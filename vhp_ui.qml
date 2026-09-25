import QtQuick
import QtQuick.Window

Window {
    id: window
    required property var vhp
    width: 1280
    height: 800
    visible: true
    visibility: Window.FullScreen
    color: "#000000"
    title: "VirtualHerePad"

    property bool keyboardOpen: false

    // Exact touch maths: map a point to the key that owns its grid cell. This
    // mirrors vhp_keyboard.layout_grid, where every row spans `columns` cells.
    function codeAt(x, y, w, h) {
        var rows = vhp.rows;
        var rowHeight = h / rows.length;
        var row = Math.floor(y / rowHeight);
        if (row < 0 || row >= rows.length) {
            return -1;
        }
        var cell = Math.floor(x * window.columns / w);
        var keys = rows[row];
        var acc = 0;
        for (var i = 0; i < keys.length; i++) {
            acc += keys[i].span;
            if (cell < acc) {
                return keys[i].code;
            }
        }
        return -1;
    }

    component FlatButton: Rectangle {
        id: button
        property string text: ""
        property bool highlighted: false
        signal tapped

        radius: height * 0.22
        color: highlighted ? "#1c6b3a" : (buttonMouse.pressed ? "#2b3a4a" : "#16202b")
        border.color: highlighted ? "#43d17a" : "#3a4c60"
        border.width: 2

        Text {
            anchors.centerIn: parent
            text: button.text
            color: "#e8f1f8"
            font.bold: true
            font.pixelSize: Math.max(13, button.height * 0.32)
        }
        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            onClicked: button.tapped()
        }
    }

    Item {
        id: topBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: Math.max(64, window.height * 0.12)

        FlatButton {
            id: toggleButton
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(parent.width * 0.36, 420)
            height: parent.height * 0.68
            highlighted: window.keyboardOpen
            text: window.keyboardOpen ? "HIDE KEYBOARD" : "KEYBOARD"
            onTapped: window.keyboardOpen = !window.keyboardOpen
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: vhp.shared ? "#43d17a" : "#c9a227"
            font.pixelSize: Math.max(14, topBar.height * 0.24)
            font.bold: true
            text: vhp.connected ? (vhp.shared ? "PC KEYBOARD ACTIVE" : "WAITING FOR PC") : "BACKEND OFFLINE"
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: vhp.connected ? "#8fb4d0" : "#c05a5a"
            font.pixelSize: Math.max(13, topBar.height * 0.2)
            text: "Brightness " + vhp.percent + "%   " + vhp.layoutName
        }
    }

    Column {
        id: keypad
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top
        anchors.margins: 12
        visible: window.keyboardOpen

        Repeater {
            model: vhp.rows

            delegate: Row {
                id: keyRow
                height: keypad.height / 6
                spacing: 0

                Repeater {
                    model: keyRow.modelData

                    delegate: Item {
                        width: keypad.width * modelData.span / window.columns
                        height: keyRow.height

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 3
                            radius: 10
                            color: modelData.active ? "#2f6ea8" : "#1b2632"
                            border.color: modelData.active ? "#6fb6f0" : "#2d3d4d"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                color: "#eaf2f8"
                                font.pixelSize: Math.max(11, parent.height * 0.34)
                            }
                        }
                    }
                }
            }
        }
    }

    MultiPointTouchArea {
        id: keypadTouch
        anchors.fill: keypad
        enabled: window.keyboardOpen
        minimumTouchPoints: 1
        maximumTouchPoints: 10

        property var mapping: ({})

        function sync(points) {
            var next = ({});
            for (var i = 0; i < points.length; i++) {
                var point = points[i];
                if (!point.pressed) {
                    continue;
                }
                var code = window.codeAt(point.x, point.y, keypadTouch.width, keypadTouch.height);
                if (code !== -1) {
                    next[point.id] = code;
                }
            }
            for (var id in mapping) {
                if (!(id in next) || next[id] !== mapping[id]) {
                    vhp.release(mapping[id]);
                }
            }
            for (var id2 in next) {
                if (mapping[id2] !== next[id2]) {
                    vhp.press(next[id2]);
                }
            }
            mapping = next;
        }

        onPressed: sync(touchPoints)
        onUpdated: sync(touchPoints)
        onReleased: sync(touchPoints)
        onCanceled: {
            for (var id in mapping) {
                vhp.release(mapping[id]);
            }
            mapping = ({});
        }
        Component.onDestruction: {
            for (var id in mapping) {
                vhp.release(mapping[id]);
            }
        }
    }

    Item {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Math.max(62, window.height * 0.11)
        visible: !window.keyboardOpen

        Row {
            anchors.centerIn: parent
            spacing: 10

            Repeater {
                model: vhp.layoutNames

                delegate: FlatButton {
                    height: bottomBar.height * 0.66
                    width: Math.max(96, bottomBar.width * 0.13)
                    highlighted: modelData.id === vhp.layoutName ? true : false
                    text: modelData.label
                    onTapped: vhp.setLayout(modelData.id)
                }
            }

            FlatButton {
                height: bottomBar.height * 0.66
                width: Math.max(96, bottomBar.width * 0.13)
                text: "RELEASE KEYS"
                onTapped: vhp.clear()
            }

            FlatButton {
                height: bottomBar.height * 0.66
                width: Math.max(96, bottomBar.width * 0.13)
                text: "STOP VHP"
                onTapped: vhp.stop()
            }
        }
    }
}
