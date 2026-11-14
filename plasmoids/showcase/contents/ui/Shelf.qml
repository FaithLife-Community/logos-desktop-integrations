// Covers standing on shelves, like a library's display stand.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: shelf
    required property var widget
    spacing: Kirigami.Units.smallSpacing

    readonly property real bookHeight: Kirigami.Units.gridUnit * 6.5
    readonly property real bookWidth: bookHeight * 0.68
    readonly property real plank: Kirigami.Units.smallSpacing * 2

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        Kirigami.Heading {
            Layout.fillWidth: true
            level: 3
            text: i18n("From your library")
            elide: Text.ElideRight
        }
        PlasmaComponents.BusyIndicator {
            visible: shelf.widget.loading
            running: visible
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Layout.preferredWidth
        }
        PlasmaComponents.ToolButton {
            icon.name: "media-playlist-shuffle"
            onClicked: shelf.widget.refresh(true)
            PlasmaComponents.ToolTip { text: i18n("Show different books") }
        }
    }

    GridView {
        id: grid
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: shelf.widget.books
        // Spread the books evenly across the width.
        readonly property int columns: Math.max(1, Math.floor(width / (shelf.bookWidth + Kirigami.Units.gridUnit)))
        cellWidth: width / columns
        cellHeight: shelf.bookHeight + shelf.plank + Kirigami.Units.gridUnit * 1.2
        interactive: contentHeight > height

        delegate: Item {
            required property var modelData
            required property int index
            width: grid.cellWidth
            height: grid.cellHeight

            Book {
                info: parent.modelData
                tiltEnabled: shelf.widget.tilt
                width: shelf.bookWidth
                height: shelf.bookHeight
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: plank.top
                onOpen: url => shelf.widget.backend.openUrl(url)
            }

            // The shelf plank: adjacent cells join up into one continuous shelf.
            Rectangle {
                id: plank
                // the last book on a part-filled shelf extends the plank to the far edge
                readonly property bool lastOnShelf: index === grid.count - 1
                anchors { left: parent.left; bottom: parent.bottom }
                width: lastOnShelf ? grid.width - parent.x : parent.width
                anchors.bottomMargin: Kirigami.Units.smallSpacing * 2
                height: shelf.plank
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.lighter(Kirigami.Theme.alternateBackgroundColor, 1.08) }
                    GradientStop { position: 1.0; color: Qt.darker(Kirigami.Theme.alternateBackgroundColor, 1.25) }
                }
                Rectangle {  // soft shadow under the plank
                    anchors { left: parent.left; right: parent.right; top: parent.bottom }
                    height: Kirigami.Units.smallSpacing * 2
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.18) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }
        }
    }

    PlasmaComponents.Label {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        visible: shelf.widget.books.length === 0 && !shelf.widget.loading
        text: shelf.widget.error || i18n("Nothing to show yet")
        wrapMode: Text.Wrap
        opacity: 0.7
    }
}
