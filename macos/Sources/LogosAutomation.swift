import AppKit

struct IntegrationError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
    init(_ message: String) { self.message = message }
}

@MainActor
enum LogosAutomation {
    static var bundleID: String {
        UserDefaults.standard.string(forKey: "logosBundleID") ?? "com.logos.desktop.logos"
    }
    private static func scriptString(_ text: String) -> String {
        "\"" + text.replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"") + "\""
    }
    private static var commandInProgress = false
    static func command(_ text: String) async throws {
        guard !commandInProgress else { throw IntegrationError("Another Logos command is in progress. Try again in a moment.") }
        commandInProgress = true
        defer { commandInProgress = false }
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, text.rangeOfCharacter(from: .controlCharacters) == nil else {
            throw IntegrationError("Enter a single Logos command.")
        }
        guard let appURL = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) else {
            throw IntegrationError("Logos is not installed. For Verbum, change the bundle identifier in Settings.")
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        let app = try await NSWorkspace.shared.openApplication(at: appURL, configuration: configuration)
        try await Task.sleep(nanoseconds: 700_000_000)
        let id = scriptString(bundleID)
        let source = """
        with timeout of 15 seconds
            tell application "System Events"
                set matchingProcesses to every application process whose bundle identifier is \(id)
                if (count of matchingProcesses) is 0 then error "Logos is not ready yet. Please try again after it opens."
                set logosProcess to item 1 of matchingProcesses
                set frontmost of logosProcess to true
                if frontmost of logosProcess is false then error "Could not focus Logos."
                keystroke "l" using {command down, option down}
                delay 0.4
                if frontmost of logosProcess is false then error "Logos lost focus."
                keystroke "a" using command down
                keystroke \(scriptString(text))
                delay 1
                if frontmost of logosProcess is false then error "Logos lost focus before execution."
                key code 36
            end tell
        end timeout
        """
        guard app.isFinishedLaunching else { throw IntegrationError("Logos is still starting. Try again when it is ready.") }
        var error: NSDictionary?
        guard let script = NSAppleScript(source: source) else { throw IntegrationError("Could not compile the Logos automation script.") }
        script.executeAndReturnError(&error)
        if let error { throw IntegrationError("\(error[NSAppleScript.errorMessage] ?? error). Allow Logos Desktop Integrations under System Settings → Privacy & Security → Accessibility and Automation if access was denied.") }
    }
    static func open(_ raw: String) async throws {
        guard let url = URL(string: raw), let scheme = url.scheme?.lowercased() else { throw IntegrationError("Invalid Logos link.") }
        if scheme == "logos-integrations" {
            guard ["command", "copy"].contains(url.host ?? ""), let text = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                .queryItems?.first(where: { $0.name == "q" })?.value else { throw IntegrationError("Invalid integration action.") }
            if url.host == "copy" { _ = try copyVerses(text) }
            else { try await command(text) }
            return
        }
        guard ["logos4", "logosref", "logosres", "libronixdls"].contains(scheme),
              let appURL = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) else {
            throw IntegrationError("Unsupported link or Logos is not installed.")
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        _ = try await NSWorkspace.shared.open([url], withApplicationAt: appURL, configuration: configuration)
    }
    static func copyVerses(_ reference: String) throws -> String {
        // Named pasteboard: no temporary document or simulated keyboard shortcut required.
        let board = NSPasteboard.withUniqueName()
        defer { board.releaseGlobally() }
        board.setString(reference, forType: .string)
        let service = "Logos Bible Software/Replace with Passage (Logos)"
        guard NSPerformService(service, board), let text = board.string(forType: .string),
              !text.isEmpty, text.trimmingCharacters(in: .whitespacesAndNewlines) != reference.trimmingCharacters(in: .whitespacesAndNewlines) else {
            throw IntegrationError("Logos’s Replace with Passage Service did not return text. Enable it in System Settings → Keyboard → Keyboard Shortcuts → Services. Its direct use from this integration still needs verification on a Mac.")
        }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        return text
    }
}
