package ai.mack.sarvagyan.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.os.Build
import android.util.Log
import android.util.LruCache
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.math.min

@Serializable
data class AvatarEntry(
    val id: String,
    val main: String,
    val thumb: String,
)

private val avatarJson = Json { ignoreUnknownKeys = true }

/**
 * Pure config loader/validator (also unit-tested on JVM without Android assets):
 * keeps file order from avatars.json and skips any entry whose asset file is missing.
 */
fun parseAndVerifyAvatarConfig(
    rawJson: String,
    assetExists: (String) -> Boolean,
    warn: (String) -> Unit,
): List<AvatarEntry> {
    val entries = runCatching { avatarJson.decodeFromString<List<AvatarEntry>>(rawJson) }
        .onFailure { warn("Failed to parse avatars.json: ${it.message}") }
        .getOrDefault(emptyList())
    val verified = ArrayList<AvatarEntry>(entries.size)
    for (entry in entries) {
        val mainAsset = "avatars/${entry.main}"
        val thumbAsset = "avatars/${entry.thumb}"
        val missing = when {
            !assetExists(mainAsset) -> mainAsset
            !assetExists(thumbAsset) -> thumbAsset
            else -> null
        }
        if (missing != null) {
            warn("Missing avatar asset file '$missing' for id='${entry.id}'; skipping.")
            continue
        }
        verified.add(entry)
    }
    return verified
}

class AvatarStore(
    private val context: Context,
    private val http: OkHttpClient,
    private val baseUrl: () -> String,
    private val token: () -> String? = { null },
) {
    private val memCache = LruCache<String, ImageBitmap>(48)
    private val diskDir = File(context.cacheDir, "avatars").apply { mkdirs() }
    @Volatile private var cachedCatalog: List<AvatarEntry>? = null

    fun catalog(): List<AvatarEntry> {
        cachedCatalog?.let { return it }
        val loaded = runCatching {
            val raw = context.assets.open("avatars/avatars.json").bufferedReader().use { it.readText() }
            val existing = context.assets.list("avatars")?.toSet().orEmpty()
            parseAndVerifyAvatarConfig(
                rawJson = raw,
                assetExists = { path -> path.removePrefix("avatars/") in existing },
                warn = { msg -> Log.w("AvatarConfig", msg) },
            )
        }.onFailure {
            Log.w("AvatarConfig", "Failed to read avatars/avatars.json: ${it.message}")
        }.getOrDefault(emptyList())
        cachedCatalog = loaded
        return loaded
    }

    private fun cacheKey(avatar: String, useMain: Boolean): String = "$avatar:${if (useMain) "main" else "thumb"}"

    fun peekCached(avatar: String?, useMain: Boolean): ImageBitmap? {
        if (avatar.isNullOrBlank()) return null
        return memCache.get(cacheKey(avatar, useMain))
    }

    suspend fun loadBitmap(avatar: String?, useMain: Boolean): ImageBitmap? {
        if (avatar.isNullOrBlank()) return null
        val key = cacheKey(avatar, useMain)
        memCache.get(key)?.let { return it }

        val bmp: ImageBitmap? = withContext(Dispatchers.IO) {
            when {
                avatar.startsWith("avatar-") -> {
                    val entry = catalog().firstOrNull { it.id == avatar } ?: return@withContext null
                    val fileName = if (useMain) entry.main else entry.thumb
                    val assetPath = "avatars/$fileName"
                    runCatching {
                        context.assets.open(assetPath).use { BitmapFactory.decodeStream(it)?.asImageBitmap() }
                    }.onFailure {
                        Log.w("AvatarConfig", "Missing or unreadable avatar asset '$assetPath': ${it.message}")
                    }.getOrNull()
                }
                avatar.startsWith("custom:") -> {
                    val fid = avatar.removePrefix("custom:")
                    if (!fid.matches(Regex("[0-9a-f]{32}"))) return@withContext null
                    val diskFile = File(diskDir, "${fid}_${if (useMain) "main" else "thumb"}.webp")
                    if (diskFile.isFile && diskFile.length() > 0) {
                        BitmapFactory.decodeFile(diskFile.absolutePath)?.asImageBitmap()?.let { return@withContext it }
                    }
                    val url = baseUrl().trimEnd('/') + "/v1/avatars/$fid?thumb=${!useMain}"
                    runCatching {
                        val rb = Request.Builder().url(url).get()
                        token()?.let { rb.header("Authorization", "Bearer $it") }
                        http.newCall(rb.build()).execute().use { resp ->
                            if (!resp.isSuccessful) return@use null
                            val bytes = resp.body.bytes()
                            if (bytes.isEmpty()) return@use null
                            runCatching { diskFile.writeBytes(bytes) }
                            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
                        }
                    }.getOrNull()
                }
                else -> null
            }
        }
        if (bmp != null) memCache.put(key, bmp)
        return bmp
    }

    companion object {
        /** Crops to a square centered horizontally with top bias, scales to <=512px, and compresses to WebP. */
        fun prepareAvatarUpload(context: Context, uri: Uri): ByteArray {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
                ?: error("Could not open selected image.")
            val maxDim = maxOf(bounds.outWidth, bounds.outHeight)
            var sample = 1
            while (maxDim / sample > 1024) sample *= 2

            val opts = BitmapFactory.Options().apply { inSampleSize = sample }
            var bmp = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) }
                ?: error("Could not decode selected image.")

            val orientation = runCatching {
                context.contentResolver.openInputStream(uri)?.use {
                    ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
                } ?: ExifInterface.ORIENTATION_NORMAL
            }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)

            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            }
            if (!matrix.isIdentity) {
                val rotated = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, matrix, true)
                if (rotated !== bmp) bmp.recycle()
                bmp = rotated
            }

            val side = min(bmp.width, bmp.height)
            val left = (bmp.width - side) / 2
            val top = if (bmp.height > bmp.width) ((bmp.height - side) * 0.10f).toInt() else 0
            val squared = Bitmap.createBitmap(bmp, left, top, side, side)
            if (squared !== bmp) bmp.recycle()

            val target = min(512, squared.width)
            val finalBmp = if (squared.width != target) {
                Bitmap.createScaledBitmap(squared, target, target, true).also { squared.recycle() }
            } else {
                squared
            }

            val fmt = if (Build.VERSION.SDK_INT >= 30) Bitmap.CompressFormat.WEBP_LOSSY else @Suppress("DEPRECATION") Bitmap.CompressFormat.WEBP
            var out = ByteArray(0)
            for (q in intArrayOf(88, 78, 66, 54)) {
                val bos = ByteArrayOutputStream()
                finalBmp.compress(fmt, q, bos)
                out = bos.toByteArray()
                if (out.size <= 100 * 1024) break
            }
            finalBmp.recycle()
            return out
        }
    }
}
