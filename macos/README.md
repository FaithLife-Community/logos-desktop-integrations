# Native macOS integrations

macOS 14+ integrations for native Logos for Mac: desktop/Notification Centre
widgets, Spotlight results, Siri/Shortcuts, a selected-text Service, reading
reminders and an optional Raycast search extension. There is **no standalone
runner, library browser, dashboard, main window or Dock icon**. A background
bundle registers the native extensions, refreshes local metadata and sends
commands to Logos. Its book menu-bar icon offers Refresh, Settings and Quit.
Settings contain only configuration and diagnostic status.

## Build variants

Install full Xcode and XcodeGen (`brew install xcodegen`), then from the root:

```sh
./macos/build.sh
./macos/build.sh --without-local-data
```

The latter clears `LOGOS_LOCAL_DATA` for **both host and widget extension**.
Folder discovery, SQLite access, metadata indexing, reminders and data-derived
widgets are compiled out. It cannot be re-enabled through a runtime preference.
The variant also ignores previous metadata caches and clears this bundle's old
Spotlight entries and reading reminders. Commands, manually named layouts,
Siri/Shortcuts, selected-text lookup, verse replacement, the configurable command
widget and Verse of the Day remain available.

Full builds find Logos under `~/Library/Application Support/Logos4`, `Logos` or
`Verbum`; override the directory containing Data/Documents in Settings. SQLite
connections are read-only. Protected book resources are never opened. Catalog,
priority, reading-plan, history, Factbook and sermon metadata queries follow the
Plasma implementation. Thumbnails are capped to avoid loading a whole library's
artwork. Refresh happens every five minutes while the background host runs.

The generated project is `macos/LogosDesktopIntegrations.xcodeproj`. For widgets
that display shared local metadata, sign both targets with your developer team
and a provisioned App Group, setting `SHARED_GROUP_IDENTIFIER` accordingly.
The unsigned compiler command is `./macos/build.sh CODE_SIGNING_ALLOWED=NO`.
CI produces universal ad hoc signed test ZIPs without App Group entitlements:
command widgets and Verse of the Day do not need shared metadata; **reading-plan
and showcase widgets require the provisioned build**. The menu-bar Settings
reports whether sharing is available. No signing credentials are stored here.

## Install and use

Unzip the selected build and copy `LogosDesktopIntegrations.app` to Applications.
Open it once; no main window appears. Use its menu-bar Settings to configure
access. macOS may require Open Anyway for an ad hoc preview. Permit **Logos
Desktop Integrations** under Privacy & Security → Accessibility and Automation.
Terminal's permissions do not transfer. To keep it running after login, add it
under System Settings → General → Login Items.

* **Widgets:** add Logos widgets in the macOS widget gallery. Edit the command
  widget's title and exact command (for example `open passage study layout`).
  Edit Reading Plans to choose Today/Anytime; edit Showcase to choose unread
  books, sermon commentaries or both. Verse of the Day fetches the same public
  Biblia artwork and passage link as Plasma. Data widgets display covers,
  progress, estimated minutes and overdue/streak details where available.
* **Spotlight:** a full build indexes library metadata and saved layouts locally.
  Selecting a result opens it in Logos. Disable this in Settings if unwanted.
  Spotlight does not accept arbitrary live KRunner plugins; App Shortcuts
  expose actions, and Raycast supplies the richer live command/result list.
* **Siri/Shortcuts:** Open Passage, Search Factbook, Open Layout, Open My
  Devotional, Run Command, Copy Bible Verses and Look Up Clipboard. Set the
  devotional command in Settings. Create a personally named Shortcut such as
  "Open my devotional" for a shorter spoken phrase; app-supplied phrases
  include the integration's name. Unrestricted natural-language interpretation
  is not promised.
* **Services:** select text in another application and use Services → Look up
  in Logos. Assign a shortcut under Keyboard → Keyboard Shortcuts → Services.
  References open in Logos; single words open Bible Word Study. Copy Bible
  Verses calls Logos's native Replace with Passage Service and returns plain
  text through Shortcuts and the clipboard; no TextEdit automation is used.
* **Reminders:** opt in under Settings. Reading-plan notification times become
  native notifications with a Read now action. Keep the host running to track
  completed readings and update the next reading.

Commands activate Logos, press **⌘⌥L**, enter one escaped command and Return.
This route and `open passage study layout` were verified on a user's Mac;
passage links and keyboard-triggered Replace with Passage were also verified.
Other command strings, direct Service invocation, full database compatibility,
Spotlight routing and widget interactions still need real-device acceptance.
Errors are shown in menu-bar status, rather than claimed as successful results.

## Optional Raycast extension

In `macos/raycast`, run `npm ci` then `npm run dev` on a Mac with Raycast, or
import the extension through Raycast development tools. Set its host path if
not installed at `/Applications/LogosDesktopIntegrations.app`.

It calls the host's headless `--query-json` interface and opens the returned
native links. Inputs mirror Plasma: `o John 3:16`, `oesv John 3:16`, `s grace`,
`ol bavinck`, `lex agape`, `fb Moses`, `lay`, `lay passage study`, `rp`, `today`,
`or`, `cv John 3:16`, or `cmd` followed by an exact Logos command. Metadata
results require the full host running; commands-only builds retain named
commands without reading a previous full build's cache. No shell interpolation
of search text is used. The headless interface does not start a second host.

## Validation and remaining differences

CI compiles both variants for arm64/x86_64, verifies the disabled reader and
widget kinds are absent from commands-only binaries, checks LSUIElement,
embedded widgets and the headless command path, and type-checks/builds Raycast.

Real-device acceptance: confirm no Dock/main window, select a Spotlight book
and layout, run Siri actions, use selection/verse Services, try Raycast results,
configure all widget modes in a provisioned build, and switch from full to
commands-only to check stale metadata features disappear. Plasma's custom TOML
aliases and Logos COM panel inspection are not ported; structured sermon
passages work, but extracting passages from sermon titles is not yet supported.

Community project, not affiliated with Faithlife. GPL-3.0-or-later.
