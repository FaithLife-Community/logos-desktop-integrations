import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property string cfg_clickAction
    property alias cfg_bible: bibleField.text
    property alias cfg_customUrl: customField.text
    property alias cfg_sourceUrl: sourceField.text
    // cached data, not shown
    property string cfg_lastImage
    property string cfg_lastReference
    property string cfg_lastText
    property string cfg_lastLogosUrl
    property string cfg_lastFetchedDate

    Kirigami.FormLayout {
        QQC2.ComboBox {
            id: actionBox
            Kirigami.FormData.label: i18n("Click opens:")
            textRole: "text"
            valueRole: "value"
            model: [
                { text: i18n("The verse in a Bible"), value: "bible" },
                { text: i18n("Passage Guide"), value: "passageGuide" },
                { text: i18n("Exegetical Guide"), value: "exegeticalGuide" },
                { text: i18n("Custom Logos URL"), value: "custom" }
            ]
            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(cfg_clickAction))
            onActivated: cfg_clickAction = currentValue
        }
        QQC2.TextField {
            id: bibleField
            Kirigami.FormData.label: i18n("Bible:")
            enabled: actionBox.currentValue === "bible"
            placeholderText: i18n("ESV (from the site), or a logosres id e.g. lgcystndrdbblsb")
        }
        QQC2.TextField {
            id: customField
            Kirigami.FormData.label: i18n("Custom URL:")
            enabled: actionBox.currentValue === "custom"
            placeholderText: "logos4:Guide;t=My_Passage_Guide;ref={ref}"
        }
        QQC2.Label {
            text: i18n("{ref} is replaced with the verse, e.g. BibleESV.Ro6.4")
            font: Kirigami.Theme.smallFont
            opacity: 0.7
        }
        QQC2.TextField {
            id: sourceField
            Kirigami.FormData.label: i18n("Source page:")
        }
    }
}
