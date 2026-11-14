import QtQuick

Item {
    id: character
    objectName: "characterAnimation"
    property bool playing: true
    property int frameIndex: 0
    function gesture() {
        if (playing)
            cycle.restart()
    }
    Image {
        anchors.centerIn: parent
        width: 320; height: 320
        source: "qrc:/assets/puppet-motion.png"
        sourceClipRect: Qt.rect((character.frameIndex % 3) * 512,
                               Math.floor(character.frameIndex / 3) * 512, 512, 512)
        smooth: false
        mipmap: false
    }
    // Brief closing/opening frames keep the blink short; the resting pose
    // holds between gestures instead of continuously waving at the user.
    SequentialAnimation {
        id: cycle
        running: true
        paused: !character.playing
        loops: Animation.Infinite
        PropertyAction { target: character; property: "frameIndex"; value: 1 }
        PauseAnimation { duration: 160 }
        PropertyAction { target: character; property: "frameIndex"; value: 2 }
        PauseAnimation { duration: 100 }
        PropertyAction { target: character; property: "frameIndex"; value: 3 }
        PauseAnimation { duration: 110 }
        PropertyAction { target: character; property: "frameIndex"; value: 4 }
        PauseAnimation { duration: 160 }
        PropertyAction { target: character; property: "frameIndex"; value: 5 }
        PauseAnimation { duration: 160 }
        PropertyAction { target: character; property: "frameIndex"; value: 0 }
        PauseAnimation { duration: 2300 }
    }
}
