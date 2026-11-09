package ai.mack.sarvagyan.ui.screens

import ai.mack.sarvagyan.BuildConfig

/** The privacy policy shown in the app. Keep in step with docs/PRIVACY.md (the public web version). */
object PrivacyPolicy {
    val sections: List<Pair<String, String>> = buildList {
        add("In short" to "Sarvagyan translates your calls, voicemail and chats. To do that, your words are processed by our " +
            "server and by the speech and translation services below. We keep as little as possible, for as short a time as possible. " +
            "Calls are never recorded. No ads, no selling of data, no tracking.")
        add("What we keep, and for how long" to listOf(
            "Account: name, @username, email (none for guests), language. Until you delete your account.",
            "Password: only as a scrambled hash we cannot read.",
            "Signed-in devices: phone model and last use. 30 days after last use, or until signed out.",
            "Contacts, blocked people, favourites: until you remove them.",
            "Call history: who, when, how long, which languages. No audio, ever.",
            "Voicemail: the recognised text and its translation, until deleted, at most 7 days. The recording is discarded at once.",
            "Chat messages and voice messages: 7 days, 30 days or 1 year, the shortest setting among the chat's members.",
        ).joinToString("\n") { "• $it" })
        add("Only on your phone" to "Call transcripts, if you turn on \"Save transcripts\" (off by default). They are encrypted on " +
            "the phone and you can delete them in Settings → Storage and data.")
        add("Who else processes your words" to "To translate, what you say or type is sent, without your name or account " +
            "details, to Gnani.ai (speech recognition and the translated voice, India) and MyMemory / Translated (text translation, " +
            "Italy). Their own privacy terms apply to that processing. The original voices of a call travel directly between the " +
            "two phones, encrypted.")
        add("Your choices" to listOf(
            "Delete your account and all its server data: Settings → Account → Delete account. It happens at once.",
            "Turn read receipts off, choose how long chats are kept: Settings → Chats.",
            "Choose who can call you, block people: Contacts.",
            "Sign out lost or old phones: Settings → Account → Signed-in devices.",
            "Lock the app and block screenshots: Settings → Privacy and security.",
        ).joinToString("\n") { "• $it" })
        add("Security" to "All connections are encrypted. Sign-ins renew every 15 minutes and can be ended from any of your " +
            "phones. Repeated wrong passwords lock sign-in for 15 minutes. Our server logs never contain what you say or write.")
        add("Children" to "Sarvagyan is not meant for children under 13.")
        if (BuildConfig.PRIVACY_CONTACT.isNotBlank()) add("Contact" to "Questions or requests about your data: ${BuildConfig.PRIVACY_CONTACT}")
    }
}
