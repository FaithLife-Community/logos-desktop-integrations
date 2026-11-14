import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var allBooks: []
    readonly property var books: allBooks.filter(b => Plasmoid.configuration.hiddenBooks.indexOf(b.resourceId) < 0)
    property bool loading: false
    property string error: ""
    property string loadedDate: ""
    readonly property bool tilt: Plasmoid.configuration.tilt
    readonly property string shelfMode: Plasmoid.configuration.shelf  // library · sermon · both
    readonly property bool sermonShelf: shelfMode === "sermon"
    readonly property bool hasSermon: shelfMode !== "library"
    readonly property bool hasLibrary: shelfMode !== "sermon"
    onShelfModeChanged: refresh(false)
    property alias backend: backend

    function today() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function hideBook(resourceId) {
        const hidden = Plasmoid.configuration.hiddenBooks.slice()
        if (hidden.indexOf(resourceId) < 0)
            hidden.push(resourceId)
        Plasmoid.configuration.hiddenBooks = hidden
    }

    function refresh(shuffle) {
        loading = true
        backend.run("showcase", "--showcase " + Plasmoid.configuration.bookCount
                    + (shelfMode === "sermon" ? " --sermon" : shelfMode === "both" ? " --sermon --library" : "") + (shuffle ? " --shuffle" : ""))
    }

    Backend {
        id: backend
        onFinished: (tag, stdout, exitCode) => {
            if (tag !== "showcase")
                return
            root.loading = false
            try {
                root.allBooks = JSON.parse(stdout)
                root.error = ""
                root.loadedDate = root.today()
            } catch (e) {
                root.error = i18n("Couldn't read your library. Is logos-plasma installed?")
            }
        }
    }

    Plasmoid.icon: "bookcase"
    Plasmoid.backgroundHints: PlasmaCore.Types.DefaultBackground | PlasmaCore.Types.ConfigurableBackground
    toolTipMainText: i18n("Logos Showcase")
    toolTipSubText: sermonShelf ? i18n("Your commentaries for your sermon passage")
                  : shelfMode === "both" ? i18n("Your sermon commentaries and well-rated books you haven't read")
                                : i18n("Well-rated books you own but haven't read")

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            visible: root.hasLibrary
            text: i18n("Show different books")
            icon.name: "media-playlist-shuffle"
            onTriggered: root.refresh(true)
        }
    ]

    preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar ? fullRepresentation : compactRepresentation

    compactRepresentation: Kirigami.Icon {
        source: "bookcase"
        fallback: "accessories-dictionary"
        active: mouse.containsMouse
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.expanded = !root.expanded
        }
    }

    fullRepresentation: Shelf {
        widget: root
        Layout.preferredWidth: Kirigami.Units.gridUnit * 28
        Layout.preferredHeight: Kirigami.Units.gridUnit * 20
        Layout.minimumWidth: Kirigami.Units.gridUnit * 8
        Layout.minimumHeight: Kirigami.Units.gridUnit * 10
    }

    onExpandedChanged: if (expanded && loadedDate !== today()) refresh(false)

    // A new shelf each day (checked every 10 minutes; no network involved).
    Timer {
        interval: 10 * 60 * 1000
        running: true
        repeat: true
        onTriggered: if (root.loadedDate !== root.today()) root.refresh(false)
    }

    Component.onCompleted: refresh(false)
}
