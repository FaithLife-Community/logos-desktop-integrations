// One set of shelves: covers standing on planks that join into a continuous shelf.
import QtQuick
import org.kde.kirigami as Kirigami

GridView {
    id: grid
    property var shelf
    property bool fillLastPlank: true
    clip: true
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
            readonly property bool lastOnShelf: grid.fillLastPlank && index === grid.count - 1
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
