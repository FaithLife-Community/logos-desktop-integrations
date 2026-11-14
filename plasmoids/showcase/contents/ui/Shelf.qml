// Covers standing on shelves, like a library's display stand. Shows the library shelf
// (unread, well rated), the sermon shelf (your commentaries for the sermon passage) or both,
// half and half.
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

    readonly property var sermonBooks: widget.books.filter(b => !!b.sermon)
    readonly property var libraryBooks: widget.books.filter(b => !b.sermon)
    readonly property var sermon: sermonBooks.length ? sermonBooks[0].sermon : null
    readonly property bool both: widget.hasSermon && widget.hasLibrary
    readonly property string sermonWhen: sermon ? (sermon.date
        ? i18n("%1 · %2", sermon.passage, Qt.formatDate(new Date(sermon.date + "T12:00:00"), "ddd d MMM"))
        : sermon.passage) : ""

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        Kirigami.Heading {
            Layout.fillWidth: true
            level: 3
            text: shelf.widget.hasLibrary ? i18n("From your library") : i18n("For your sermon")
            elide: Text.ElideRight
        }
        PlasmaComponents.BusyIndicator {
            visible: shelf.widget.loading
            running: visible
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Layout.preferredWidth
        }
        PlasmaComponents.ToolButton {
            visible: shelf.widget.hasLibrary
            icon.name: "media-playlist-shuffle"
            onClicked: shelf.widget.refresh(true)
            PlasmaComponents.ToolTip { text: i18n("Show different books") }
        }
    }

    // ── Sermon shelf ──
    PlasmaComponents.Label {
        visible: shelf.sermon !== null
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        opacity: 0.8
        elide: Text.ElideRight
        text: shelf.both ? i18n("For your sermon on %1", shelf.sermonWhen) : shelf.sermonWhen
    }
    ShelfGrid {
        id: sermonGrid
        visible: shelf.sermon !== null
        shelf: shelf
        adaptive: true
        model: shelf.sermonBooks  // every commentary; scrolls if they don't all fit
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 1  // equal share with the library shelf when both are shown
    }

    // ── Library shelf ──
    PlasmaComponents.Label {
        visible: shelf.both && shelf.libraryBooks.length > 0
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        opacity: 0.8
        text: i18n("Unread and well rated")
    }
    ShelfGrid {
        id: libraryGrid
        visible: shelf.widget.hasLibrary && shelf.libraryBooks.length > 0
        shelf: shelf
        adaptive: true
        model: shelf.libraryBooks.slice(0, Math.max(columns, fits))  // whole rows
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 1
    }

    PlasmaComponents.Label {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        visible: !shelf.widget.loading && (shelf.widget.books.length === 0
                 || (shelf.widget.sermonShelf && shelf.sermon === null))
        text: shelf.widget.error || (shelf.widget.hasSermon && shelf.sermon === null
              ? i18n("No sermon document with a passage found, or no commentaries you've rated for it")
              : i18n("Nothing to show yet"))
        wrapMode: Text.Wrap
        opacity: 0.7
    }
}
