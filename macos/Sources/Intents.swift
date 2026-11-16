import AppKit
import AppIntents

struct OpenPassageIntent: AppIntent {
    static var title: LocalizedStringResource = "Open a passage"
    static var description = IntentDescription("Open a passage in Logos’s preferred Bible.")
    static var openAppWhenRun = true
    @Parameter(title: "Passage") var passage: String
    @MainActor func perform() async throws -> some IntentResult {
        try await LogosAutomation.command("open \(passage)")
        return .result()
    }
}
struct FactbookIntent: AppIntent {
    static var title: LocalizedStringResource = "Search Factbook"
    static var openAppWhenRun = true
    @Parameter(title: "Topic") var topic: String
    @MainActor func perform() async throws -> some IntentResult {
        try await LogosAutomation.command("open Factbook to \(topic)")
        return .result()
    }
}
struct OpenLayoutIntent: AppIntent {
    static var title: LocalizedStringResource = "Open a Logos layout"
    static var openAppWhenRun = true
    @Parameter(title: "Layout name") var layout: String
    @MainActor func perform() async throws -> some IntentResult {
        let name = layout.trimmingCharacters(in: .whitespacesAndNewlines)
        try await LogosAutomation.command("open \(name)" + (name.lowercased().hasSuffix(" layout") ? "" : " layout"))
        return .result()
    }
}
struct DevotionalIntent: AppIntent {
    static var title: LocalizedStringResource = "Open my devotional"
    static var openAppWhenRun = true
    @MainActor func perform() async throws -> some IntentResult {
        guard let command = UserDefaults.standard.string(forKey: "devotionalCommand"), !command.isEmpty else {
            throw IntegrationError("Set ‘My devotional command’ in Logos Desktop Integrations Settings first.")
        }
        try await LogosAutomation.command(command)
        return .result()
    }
}
struct RunCommandIntent: AppIntent {
    static var title: LocalizedStringResource = "Run a Logos command"
    static var openAppWhenRun = true
    @Parameter(title: "Command") var command: String
    @MainActor func perform() async throws -> some IntentResult {
        try await LogosAutomation.command(command)
        return .result()
    }
}
struct CopyVersesIntent: AppIntent {
    static var title: LocalizedStringResource = "Copy Bible verses"
    static var openAppWhenRun = true
    @Parameter(title: "Passage") var passage: String
    @MainActor func perform() async throws -> some IntentResult & ReturnsValue<String> {
        .result(value: try LogosAutomation.copyVerses(passage))
    }
}
struct ClipboardLookupIntent: AppIntent {
    static var title: LocalizedStringResource = "Look up clipboard in Logos"
    static var openAppWhenRun = true
    @MainActor func perform() async throws -> some IntentResult {
        guard let text = NSPasteboard.general.string(forType: .string), !text.isEmpty else {
            throw IntegrationError("The clipboard has no text.")
        }
        try await LogosAutomation.command(Runner.lookupCommand(text))
        return .result()
    }
}
struct LogosShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: OpenPassageIntent(), phrases: ["Open a passage in \(.applicationName)"], shortTitle: "Open passage", systemImageName: "book")
        AppShortcut(intent: FactbookIntent(), phrases: ["Search Factbook in \(.applicationName)"], shortTitle: "Factbook", systemImageName: "magnifyingglass")
        AppShortcut(intent: OpenLayoutIntent(), phrases: ["Open a layout in \(.applicationName)"], shortTitle: "Open layout", systemImageName: "rectangle.3.group")
        AppShortcut(intent: DevotionalIntent(), phrases: ["Open my devotional in \(.applicationName)"], shortTitle: "My devotional", systemImageName: "sunrise")
        AppShortcut(intent: RunCommandIntent(), phrases: ["Run a command in \(.applicationName)"], shortTitle: "Run command", systemImageName: "command")
        AppShortcut(intent: CopyVersesIntent(), phrases: ["Copy Bible verses with \(.applicationName)"], shortTitle: "Copy verses", systemImageName: "doc.on.clipboard")
        AppShortcut(intent: ClipboardLookupIntent(), phrases: ["Look up clipboard in \(.applicationName)"], shortTitle: "Look up clipboard", systemImageName: "text.magnifyingglass")
    }
}
