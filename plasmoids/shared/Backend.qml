// Shared by both widgets (install.sh copies it into each package's contents/ui).
// Runs the logos-plasma backend through Plasma's executable engine.
import QtQuick
import org.kde.plasma.plasma5support as P5Support

P5Support.DataSource {
    id: exec
    engine: "executable"
    connectedSources: []

    // Installed by install.sh; $HOME is expanded by the shell the engine uses.
    readonly property string backend: 'python3 "$HOME/.local/share/logos-plasma/logos_plasma.py"'
    property var pending: ({})

    signal finished(string tag, string stdout, int exitCode)

    function quote(s) {
        return "'" + String(s).replace(/'/g, "'\\''") + "'"
    }

    function run(tag, args) {
        // A unique suffix lets the same command run again while an earlier one is connected.
        const cmd = backend + " " + args + " # " + tag + " " + Date.now()
        pending[cmd] = tag
        connectSource(cmd)
    }

    // Open a logos4:/logosres: URL via the runner service (no terminal; Logos is raised).
    function openUrl(url) {
        run("open", "--open " + quote(url))
    }

    onNewData: (sourceName, data) => {
        const tag = pending[sourceName] || ""
        delete pending[sourceName]
        disconnectSource(sourceName)
        finished(tag, data["stdout"] || "", data["exit code"] || 0)
    }
}
