import AppKit
import CoreSpotlight
import SwiftUI

@main
struct IntegrationsApp: App {
    @NSApplicationDelegateAdaptor(IntegrationsDelegate.self) private var delegate
    init() {
        // Raycast consumes results without starting another UI or a second background host.
        if CommandLine.arguments.count >= 3, CommandLine.arguments[1] == "--query-json" {
            let query = CommandLine.arguments[2]
            var items = SearchCache.read()
            #if LOGOS_LOCAL_DATA
            let parts = query.split(maxSplits: 1, whereSeparator: \.isWhitespace)
            if parts.count == 2, ["fb", "factbook"].contains(String(parts[0]).lowercased()) {
                items += (try? LocalLogosData.factbook(String(parts[1]), root: UserDefaults.standard.string(forKey: "logosDataRoot") ?? "")) ?? []
            }
            #endif
            let results = Runner.actions(query, items: items).map { action -> [String: String] in
                let url = action.isURL ? action.value : SharedStore.actionURL(action.value, kind: action.isCopy ? "copy" : "command")
                return ["id": action.id, "title": action.title, "subtitle": action.detail, "url": url]
            }
            if let data = try? JSONEncoder().encode(results) { FileHandle.standardOutput.write(data) }
            exit(0)
        }
    }
    var body: some Scene {
        Settings { IntegrationSettings(model: delegate.model) }
        MenuBarExtra("Logos integrations", systemImage: "book.closed") {
            IntegrationMenu(model: delegate.model)
        }
    }
}

struct IntegrationMenu: View {
    @ObservedObject var model: IntegrationModel
    var body: some View {
        Text(model.status).lineLimit(3)
        Divider()
        Button("Refresh integrations") { model.refresh() }
        SettingsLink { Text("Settings…") }
        Button("Quit integrations") { NSApp.terminate(nil) }
    }
}

struct IntegrationSettings: View {
    @ObservedObject var model: IntegrationModel
    @AppStorage("logosBundleID") private var bundleID = "com.logos.desktop.logos"
    @AppStorage("devotionalCommand") private var devotional = ""
    #if LOGOS_LOCAL_DATA
    @AppStorage("logosDataRoot") private var root = ""
    @AppStorage("spotlightEnabled") private var spotlight = true
    @AppStorage("remindersEnabled") private var reminders = false
    #endif
    var body: some View {
        Form {
            TextField("Logos bundle identifier", text: $bundleID)
            TextField("My devotional command", text: $devotional)
            Text("Example: open morning devotional layout. Used by the devotional Shortcut and Siri action.")
                .font(.caption).foregroundStyle(.secondary)
            #if LOGOS_LOCAL_DATA
            TextField("Logos data folder (blank = automatic)", text: $root)
            Toggle("Library and layouts in Spotlight", isOn: $spotlight)
            Toggle("Reading-plan reminders", isOn: $reminders)
            #else
            Text("Logos-folder access is compiled out in this build.")
            #endif
            Button("Apply and refresh") { model.refresh() }
            Text(model.status).font(.caption).textSelection(.enabled)
            Text(SharedStore.container == nil ? "Shared-data widgets require signing both targets with your provisioned App Group. Configurable command and Verse of the Day widgets do not use shared data." : "Widget sharing is available.")
                .font(.caption).foregroundStyle(.secondary)
            Text("Allow Logos Desktop Integrations under Privacy & Security → Accessibility and Automation. Configure widgets in the macOS widget gallery; actions appear in Shortcuts and Services.")
                .font(.caption).foregroundStyle(.secondary)
        }.formStyle(.grouped).frame(width: 560, height: 420)
    }
}

@MainActor
final class IntegrationsDelegate: NSObject, NSApplicationDelegate {
    let model = IntegrationModel()
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.servicesProvider = self
        NSUpdateDynamicServices()
        model.startRefreshing()
    }
    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls { model.execute(RunnerAction(title: "Logos action", value: url.absoluteString, isURL: true)) }
    }
    func application(_ application: NSApplication, continue userActivity: NSUserActivity,
                     restorationHandler: @escaping ([NSUserActivityRestoring]) -> Void) -> Bool {
        guard userActivity.activityType == CSSearchableItemActionType,
              let url = userActivity.userInfo?[CSSearchableItemActivityIdentifier] as? String else { return false }
        model.execute(RunnerAction(title: "Spotlight result", value: url, isURL: true))
        return true
    }
    @objc func lookupSelection(_ pasteboard: NSPasteboard, userData: String?, error: AutoreleasingUnsafeMutablePointer<NSString?>) {
        guard let text = pasteboard.string(forType: .string), !text.isEmpty else {
            error.pointee = "No selected text was supplied."; return
        }
        model.execute(RunnerAction(title: "Selected text", value: Runner.lookupCommand(text)))
    }
}
