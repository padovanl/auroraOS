/* Aurora's installer header (Calamares "sidebar", placed on top: see
   branding.desc). The logo and name on the left, and the steps as a row of
   dots joined by a line: done ones filled with a tick, the current one glowing
   with its name in white, the rest dim. Nothing here needs the keyboard. */
import io.calamares.ui 1.0
import io.calamares.core 1.0

import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: header
    height: 80
    color: "#14101e"

    readonly property color accent: "#a970ff"
    readonly property color rose: "#ff6f91"
    readonly property color dim: "#3a3150"
    readonly property color text: "#cfc7dd"
    readonly property int current: ViewManager.currentStepIndex

    // A hairline under the header, fading at the ends.
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.12) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 22
        anchors.rightMargin: 26
        spacing: 28

        RowLayout {
            spacing: 10
            Layout.alignment: Qt.AlignVCenter
            Image {
                source: "file:/" + Branding.imagePath(Branding.ProductLogo)
                sourceSize.width: 40
                sourceSize.height: 40
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
            }
            Text {
                text: Branding.string(Branding.ShortProductName)
                color: "#ffffff"
                font.pixelSize: 19
                font.weight: Font.DemiBold
                font.letterSpacing: 0.5
            }
        }

        // The steps.
        Row {
            id: steps
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            readonly property int count: repeater.count
            readonly property real cell: count > 0 ? width / count : width

            Repeater {
                id: repeater
                model: ViewManager
                Item {
                    width: steps.cell
                    height: 56
                    readonly property bool done: index < header.current
                    readonly property bool now: index === header.current

                    // Line to the next step.
                    Rectangle {
                        visible: index < steps.count - 1
                        x: parent.width / 2 + 13
                        y: 12
                        width: parent.width - 26
                        height: 2
                        radius: 1
                        color: done ? header.accent : header.dim
                        Behavior on color { ColorAnimation { duration: 250 } }
                    }
                    // Glow behind the current step.
                    Rectangle {
                        visible: now
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 0
                        width: 26; height: 26; radius: 13
                        color: Qt.rgba(0.66, 0.44, 1.0, 0.28)
                    }
                    Rectangle {
                        id: dot
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: now ? 3 : 5
                        width: now ? 20 : 16
                        height: width
                        radius: width / 2
                        border.width: (done || now) ? 0 : 2
                        border.color: header.dim
                        gradient: Gradient {
                            GradientStop { position: 0; color: (done || now) ? header.accent : "#14101e" }
                            GradientStop { position: 1; color: now ? header.rose : ((done) ? header.accent : "#14101e") }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: done
                            text: "✓"
                            color: "white"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 32
                        width: parent.width - 6
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: display
                        color: now ? "#ffffff" : (done ? header.text : "#8d8399")
                        font.pixelSize: 12
                        font.weight: now ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }
}
