/* Aurora OS installer slideshow (shown while files are copied). */
import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation

    Timer {
        interval: 7000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    component AuroraSlide: Slide {
        property string heading
        property string body
        property string glyph

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#1b1428" }
                GradientStop { position: 1.0; color: "#0d0a14" }
            }
        }
        Text {
            id: glyphText
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.18
            text: glyph
            font.pixelSize: 64
            color: "#ffa45c"
        }
        Text {
            id: headingText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: glyphText.bottom
            anchors.topMargin: 24
            text: heading
            font.pixelSize: 30
            font.weight: Font.DemiBold
            color: "#f2eefa"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: headingText.bottom
            anchors.topMargin: 16
            width: parent.width * 0.7
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: body
            font.pixelSize: 17
            lineHeight: 1.3
            color: "#cfc7dd"
        }
    }

    AuroraSlide {
        glyph: "✦"
        heading: qsTr("Welcome to Aurora OS")
        body: qsTr("A beautiful, fast desktop built on the rock-solid Debian base. Sit back — this takes a few minutes.")
    }
    AuroraSlide {
        glyph: "⌘"
        heading: qsTr("Built for developers")
        body: qsTr("Git, compilers, Python, Node.js, containers and a modern terminal are ready out of the box. Dev Hub installs the rest in one click.")
    }
    AuroraSlide {
        glyph: "◐"
        heading: qsTr("Make it yours")
        body: qsTr("Move the dock and panel, pick layouts, accent colors, fonts and themes. Everything lives in Settings.")
    }
    AuroraSlide {
        glyph: "⚡"
        heading: qsTr("Find anything with Super")
        body: qsTr("Tap the Super key to launch apps, open settings, search files, do quick math or run commands.")
    }
    AuroraSlide {
        glyph: "🛡"
        heading: qsTr("Secure and up to date")
        body: qsTr("Security updates install automatically, the firewall is on, and your data never leaves your machine.")
    }
}
