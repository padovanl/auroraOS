/* Aurora's keyboard page for the installer (Calamares' keyboardq module).

   Layouts, their variants, and "Detect…": which letters start the top row
   (QWERTY, QWERTZ, AZERTY, ЙЦУКЕН), then which character sits on one or two
   keys; the layout found is selected. Choosing a layout in the models
   (currentIndex) is what the module applies and installs.

   Everything works by clicking: Calamares shows QML pages in a widget that
   never gets the keyboard, so a search field or a "try your keyboard" field
   would take no typing here.

   Calamares' translations don't know these strings, so the page carries its
   own for Aurora's languages (tr()). */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: page
    width: 800
    height: 560
    color: "#1a1625"

    readonly property color fg: "#f2eefa"
    readonly property color muted: "#b3aac6"
    readonly property color field: "#221d30"
    readonly property color line: "#3a3150"
    readonly property color accent: "#a970ff"

    // --- words -------------------------------------------------------------------
    readonly property string lang: (Qt.uiLanguage || Qt.locale().name).replace("-", "_")
    readonly property var words: ({
        "Keyboard layout": {it: "Layout della tastiera", es: "Distribución del teclado", de: "Tastaturbelegung", fr: "Disposition du clavier", pt: "Layout do teclado", ru: "Раскладка клавиатуры", zh_CN: "键盘布局", ja: "キーボード配列", hi: "कीबोर्ड लेआउट", ar: "تخطيط لوحة المفاتيح"},
        "Choose your keyboard, or let Aurora find it for you.": {it: "Scegli la tua tastiera, o lascia che Aurora la trovi per te.", es: "Elige tu teclado, o deja que Aurora lo encuentre por ti.", de: "Wähle deine Tastatur oder lass Aurora sie für dich finden.", fr: "Choisissez votre clavier, ou laissez Aurora le trouver pour vous.", pt: "Escolha o seu teclado, ou deixe o Aurora encontrá-lo.", ru: "Выберите клавиатуру или позвольте Aurora найти её.", zh_CN: "选择你的键盘，或让 Aurora 帮你识别。", ja: "キーボードを選ぶか、Aurora に見つけてもらいましょう。", hi: "अपना कीबोर्ड चुनें, या Aurora को इसे खोजने दें।", ar: "اختر لوحة مفاتيحك، أو دع Aurora يعثر عليها."},
        "Detect…": {it: "Rileva…", es: "Detectar…", de: "Erkennen…", fr: "Détecter…", pt: "Detetar…", ru: "Определить…", zh_CN: "检测…", ja: "検出…", hi: "पहचानें…", ar: "اكتشاف…"},
        "Not sure which one you have?": {it: "Non sai quale hai?", es: "¿No sabes cuál tienes?", de: "Nicht sicher, welche du hast?", fr: "Vous ne savez pas lequel vous avez ?", pt: "Não sabe qual tem?", ru: "Не знаете, какая у вас?", zh_CN: "不确定是哪一种？", ja: "どれかわかりませんか？", hi: "पक्का नहीं कि आपका कौन-सा है?", ar: "لست متأكدًا من نوعها؟"},
        "Which letters start the top row of letters?": {it: "Con quali lettere inizia la prima riga di lettere?", es: "¿Con qué letras empieza la fila superior de letras?", de: "Mit welchen Buchstaben beginnt die obere Buchstabenreihe?", fr: "Par quelles lettres commence la rangée du haut ?", pt: "Com que letras começa a fila de cima?", ru: "С каких букв начинается верхний ряд букв?", zh_CN: "最上面一排字母以哪些字母开头？", ja: "文字キーの一番上の列はどの文字で始まりますか？", hi: "अक्षरों की सबसे ऊपरी पंक्ति किन अक्षरों से शुरू होती है?", ar: "بأي أحرف يبدأ صف الأحرف العلوي؟"},
        "Variant": {it: "Variante", es: "Variante", de: "Variante", fr: "Variante", pt: "Variante", ru: "Вариант", zh_CN: "变体", ja: "バリエーション", hi: "संस्करण", ar: "المتغير"},
        "Let's find your keyboard": {it: "Troviamo la tua tastiera", es: "Encontremos tu teclado", de: "Finden wir deine Tastatur", fr: "Trouvons votre clavier", pt: "Vamos encontrar o seu teclado", ru: "Найдём вашу клавиатуру", zh_CN: "来识别你的键盘", ja: "キーボードを調べましょう", hi: "आइए आपका कीबोर्ड खोजें", ar: "لنعثر على لوحة مفاتيحك"},
        "Which character is on the key to the right of L?": {it: "Quale carattere c'è sul tasto a destra della L?", es: "¿Qué carácter hay en la tecla a la derecha de la L?", de: "Welches Zeichen ist auf der Taste rechts neben L?", fr: "Quel caractère figure sur la touche à droite de L ?", pt: "Que carácter está na tecla à direita do L?", ru: "Какой символ на клавише справа от L?", zh_CN: "L 右边的键上是哪个字符？", ja: "L の右隣のキーにある文字は？", hi: "L के दाईं ओर वाली कुंजी पर कौन-सा अक्षर है?", ar: "ما الحرف الموجود على المفتاح يمين L؟"},
        "What else is on the 3 key?": {it: "Cos'altro c'è sul tasto 3?", es: "¿Qué más hay en la tecla 3?", de: "Was steht noch auf der Taste 3?", fr: "Qu'y a-t-il d'autre sur la touche 3 ?", pt: "O que mais está na tecla 3?", ru: "Что ещё изображено на клавише 3?", zh_CN: "数字 3 键上还有什么？", ja: "3 のキーにほかに何がありますか？", hi: "3 वाली कुंजी पर और क्या है?", ar: "ما الذي يوجد أيضًا على مفتاح 3؟"},
        "Is there a key with Ç?": {it: "C'è un tasto con Ç?", es: "¿Hay una tecla con Ç?", de: "Gibt es eine Taste mit Ç?", fr: "Y a-t-il une touche Ç ?", pt: "Há uma tecla com Ç?", ru: "Есть ли клавиша с Ç?", zh_CN: "有 Ç 键吗？", ja: "Ç のキーはありますか？", hi: "क्या Ç वाली कुंजी है?", ar: "هل يوجد مفتاح عليه Ç؟"},
        "What is on the key to the left of 1?": {it: "Cosa c'è sul tasto a sinistra dell'1?", es: "¿Qué hay en la tecla a la izquierda del 1?", de: "Was steht auf der Taste links neben 1?", fr: "Qu'y a-t-il sur la touche à gauche de 1 ?", pt: "O que está na tecla à esquerda do 1?", ru: "Что на клавише слева от 1?", zh_CN: "1 左边的键上是什么？", ja: "1 の左隣のキーには何がありますか？", hi: "1 के बाईं ओर वाली कुंजी पर क्या है?", ar: "ما الموجود على المفتاح يسار 1؟"},
        "Does the key to the right of P show both ü and è?": {it: "Il tasto a destra della P mostra sia ü che è?", es: "¿La tecla a la derecha de la P muestra ü y è?", de: "Zeigt die Taste rechts neben P sowohl ü als auch è?", fr: "La touche à droite de P montre-t-elle ü et è ?", pt: "A tecla à direita do P mostra ü e è?", ru: "На клавише справа от P есть и ü, и è?", zh_CN: "P 右边的键上同时有 ü 和 è 吗？", ja: "P の右隣のキーに ü と è の両方がありますか？", hi: "क्या P के दाईं ओर वाली कुंजी पर ü और è दोनों हैं?", ar: "هل يظهر على المفتاح يمين P الحرفان ü و è؟"},
        "What is on the key to the left of Backspace?": {it: "Cosa c'è sul tasto a sinistra di Backspace?", es: "¿Qué hay en la tecla a la izquierda de Retroceso?", de: "Was steht auf der Taste links neben der Rücktaste?", fr: "Qu'y a-t-il sur la touche à gauche de Retour arrière ?", pt: "O que está na tecla à esquerda de Backspace?", ru: "Что на клавише слева от Backspace?", zh_CN: "退格键左边的键上是什么？", ja: "Backspace の左隣のキーには何がありますか？", hi: "Backspace के बाईं ओर वाली कुंजी पर क्या है?", ar: "ما الموجود على المفتاح يسار مفتاح الحذف؟"},
        "Which language do you write?": {it: "In che lingua scrivi?", es: "¿En qué idioma escribes?", de: "In welcher Sprache schreibst du?", fr: "Dans quelle langue écrivez-vous ?", pt: "Em que língua escreve?", ru: "На каком языке вы пишете?", zh_CN: "你用哪种语言写作？", ja: "どの言語で書きますか？", hi: "आप किस भाषा में लिखते हैं?", ar: "بأي لغة تكتب؟"},
        "Yes": {it: "Sì", es: "Sí", de: "Ja", fr: "Oui", pt: "Sim", ru: "Да", zh_CN: "是", ja: "はい", hi: "हाँ", ar: "نعم"},
        "No": {it: "No", es: "No", de: "Nein", fr: "Non", pt: "Não", ru: "Нет", zh_CN: "否", ja: "いいえ", hi: "नहीं", ar: "لا"},
        "None of these": {it: "Nessuno di questi", es: "Ninguno", de: "Keines davon", fr: "Aucun", pt: "Nenhum", ru: "Ничего из этого", zh_CN: "都不是", ja: "どれでもない", hi: "इनमें से कोई नहीं", ar: "لا شيء مما سبق"},
        "Cancel": {it: "Annulla", es: "Cancelar", de: "Abbrechen", fr: "Annuler", pt: "Cancelar", ru: "Отмена", zh_CN: "取消", ja: "キャンセル", hi: "रद्द करें", ar: "إلغاء"},
        "Your keyboard isn't one we can recognize: choose it from the list.": {it: "Non riconosciamo questa tastiera: sceglila dall'elenco.", es: "No reconocemos este teclado: elígelo de la lista.", de: "Diese Tastatur erkennen wir nicht: Wähle sie aus der Liste.", fr: "Nous ne reconnaissons pas ce clavier : choisissez-le dans la liste.", pt: "Não reconhecemos este teclado: escolha-o da lista.", ru: "Эту клавиатуру не удалось определить: выберите её из списка.", zh_CN: "无法识别此键盘：请从列表中选择。", ja: "このキーボードは判別できません。一覧から選んでください。", hi: "यह कीबोर्ड पहचाना नहीं जा सका: सूची से चुनें।", ar: "لم نتعرّف على لوحة المفاتيح هذه: اخترها من القائمة."},
        "Found: %1": {it: "Trovata: %1", es: "Encontrado: %1", de: "Gefunden: %1", fr: "Trouvé : %1", pt: "Encontrado: %1", ru: "Найдено: %1", zh_CN: "已找到：%1", ja: "見つかりました: %1", hi: "मिला: %1", ar: "تم العثور على: %1"}
    })
    function tr(text) {
        var t = words[text]
        if (!t) return text
        return t[lang] || t[lang.split("_")[0]] || text
    }

    // --- choosing a layout by its xkb name -----------------------------------------
    Instantiator {
        id: layoutKeys
        model: config.keyboardLayoutsModel
        delegate: QtObject { property string key: model.key; property string label: model.label }
    }

    function selectLayout(key) {
        for (var i = 0; i < layoutKeys.count; i++) {
            var item = layoutKeys.objectAt(i)
            if (item && item.key === key) {
                config.keyboardLayoutsModel.currentIndex = i
                layoutList.positionViewAtIndex(i, ListView.Center)
                return item.label
            }
        }
        return ""
    }

    // --- the page --------------------------------------------------------------------
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Label {
            text: tr("Keyboard layout")
            color: fg
            font.pixelSize: 22
            font.bold: true
        }
        Label {
            text: tr("Choose your keyboard, or let Aurora find it for you.")
            color: muted
            font.pixelSize: 14
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: tr("Not sure which one you have?")
                color: page.muted
                font.pixelSize: 14
            }
            Button {
                id: detectButton
                text: tr("Detect…")
                onClicked: detector.start()
                contentItem: Label {
                    text: detectButton.text
                    color: "white"
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    implicitWidth: 120
                    implicitHeight: 36
                    radius: 18
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: detectButton.hovered ? "#b884ff" : "#a970ff" }
                        GradientStop { position: 1; color: detectButton.hovered ? "#ff85a2" : "#ff6f91" }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            AuroraList {
                id: layoutList
                Layout.fillWidth: true
                Layout.preferredWidth: 3
                Layout.fillHeight: true
                model: config.keyboardLayoutsModel
            }
            ColumnLayout {
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                Layout.fillWidth: true
                spacing: 6
                Label { text: tr("Variant"); color: muted; font.pixelSize: 13; font.bold: true }
                AuroraList {
                    id: variantList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: config.keyboardVariantsModel
                }
            }
        }

    }

    // --- building blocks -------------------------------------------------------------
    component AuroraList: Rectangle {
        property alias model: view.model
        function positionViewAtIndex(i, mode) { view.positionViewAtIndex(i, mode) }
        radius: 10
        color: page.field
        border.width: 1
        border.color: page.line
        clip: true
        ListView {
            id: view
            anchors.fill: parent
            anchors.margins: 4
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            currentIndex: model ? model.currentIndex : -1
            Component.onCompleted: if (model) positionViewAtIndex(model.currentIndex, ListView.Center)
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Qt.rgba(1, 1, 1, 0.22) }
            }
            delegate: ItemDelegate {
                id: row
                height: 32
                width: ListView.view ? ListView.view.width - 8 : 100
                highlighted: ListView.isCurrentItem
                contentItem: Label {
                    text: model.label
                    color: page.fg
                    font.pixelSize: 14
                    font.bold: row.highlighted
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 7
                    color: row.highlighted ? Qt.rgba(0.66, 0.44, 1.0, 0.38)
                                           : (row.hovered ? Qt.rgba(1, 1, 1, 0.07) : "transparent")
                }
                onClicked: {
                    view.model.currentIndex = index
                }
            }
        }
    }

    component Choice: Button {
        id: choice
        property string symbol: ""
        property string caption: ""
        contentItem: Item {
          implicitWidth: choiceColumn.implicitWidth
          implicitHeight: choiceColumn.implicitHeight
          Column {
            id: choiceColumn
            anchors.centerIn: parent
            spacing: 2
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: choice.symbol
                color: page.fg
                font.pixelSize: choice.caption === "" ? 16 : 26
                font.bold: true
            }
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: choice.caption
                visible: choice.caption !== ""
                color: page.muted
                font.pixelSize: 11
            }
          }
        }
        background: Rectangle {
            implicitWidth: 96
            implicitHeight: 64
            radius: 12
            color: choice.hovered ? Qt.rgba(0.66, 0.44, 1.0, 0.25) : page.field
            border.width: 1
            border.color: choice.hovered ? page.accent : page.line
        }
    }

    // --- detection -------------------------------------------------------------------
    // Each question: [ [symbol, caption, answer], … ]; an answer is a layout
    // (xkb name) or the next question.
    readonly property var questions: ({
        "rows": { text: "Which letters start the top row of letters?", options: [
            ["QWERTY", "", "qwerty"], ["QWERTZ", "", "qwertz"], ["AZERTY", "", "azerty"],
            ["ЙЦУКЕН", "", "ru"]] },
        "qwerty": { text: "Which character is on the key to the right of L?", options: [
            [";", "English", "usgb"], ["ò", "Italiano", "it"], ["ñ", "Español", "es"],
            ["ç", "Português", "ptbr"], ["ö", "Svenska / Suomi", "sefi"], ["ø", "Norsk", "no"],
            ["æ", "Dansk", "dk"], ["ş", "Türkçe", "tr"], ["ж", "Русский", "ru"]] },
        "usgb": { text: "What else is on the 3 key?", options: [
            ["#", "US", "us"], ["£", "UK", "gb"]] },
        "es": { text: "Is there a key with Ç?", options: [
            [tr("Yes"), "", "es"], [tr("No"), "", "latam"]] },
        "ptbr": { text: "What is on the key to the left of 1?", options: [
            ["\\ |", "Portugal", "pt"], ["' \"", "Brasil", "br"]] },
        "sefi": { text: "Which language do you write?", options: [
            ["Svenska", "", "se"], ["Suomi", "", "fi"]] },
        "qwertz": { text: "Which character is on the key to the right of L?", options: [
            ["ö", "Deutsch", "dech"], ["é", "Magyar", "hu"], ["ů", "Čeština", "cz"],
            ["ô", "Slovenčina", "sk"], ["č", "Hrvatski / Slovenščina", "hr"]] },
        "dech": { text: "Does the key to the right of P show both ü and è?", options: [
            [tr("No"), "Deutschland / Österreich", "de"], [tr("Yes"), "Schweiz", "ch"]] },
        "azerty": { text: "What is on the key to the left of Backspace?", options: [
            ["= +", "France", "fr"], ["- _", "Belgique", "be"]] }
    })

    Popup {
        id: detector
        modal: true
        focus: true
        anchors.centerIn: parent
        width: Math.min(page.width - 40, 620)
        padding: 24
        closePolicy: Popup.CloseOnPressOutside
        property string step: "rows"
        property string message: ""

        function start() {
            step = "rows"
            message = ""
            open()
        }
        function answer(value) {
            if (page.questions[value] !== undefined) {
                step = value
                return
            }
            var label = page.selectLayout(value)
            if (label === "") {
                message = tr("Your keyboard isn't one we can recognize: choose it from the list.")
                step = "done"
                return
            }
            message = tr("Found: %1").arg(label)
            step = "done"
            closeTimer.restart()
        }

        Timer { id: closeTimer; interval: 1400; onTriggered: detector.close() }

        background: Rectangle {
            radius: 18
            color: "#241e33"
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.12)
        }
        Overlay.modal: Rectangle { color: Qt.rgba(0.03, 0.02, 0.06, 0.6) }

        contentItem: ColumnLayout {
            spacing: 16

            Label {
                text: tr("Let's find your keyboard")
                color: page.fg
                font.pixelSize: 20
                font.bold: true
            }

            // Which characters are printed where.
            ColumnLayout {
                visible: page.questions[detector.step] !== undefined
                spacing: 12
                Label {
                    text: page.questions[detector.step] ? tr(page.questions[detector.step].text) : ""
                    color: page.muted
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: page.questions[detector.step] ? page.questions[detector.step].options : []
                        delegate: Choice {
                            symbol: modelData[0]
                            caption: modelData[1]
                            onClicked: detector.answer(modelData[2])
                        }
                    }
                    Choice {
                        symbol: tr("None of these")
                        onClicked: detector.answer("none")
                    }
                }
            }

            Label {
                visible: detector.message !== ""
                text: detector.message
                color: detector.step === "done" ? "#8ce99a" : "#ffb86b"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Button {
                id: cancelButton
                Layout.alignment: Qt.AlignRight
                text: tr("Cancel")
                onClicked: detector.close()
                contentItem: Label { text: cancelButton.text; color: page.fg; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle {
                    implicitWidth: 100; implicitHeight: 34; radius: 17
                    color: cancelButton.hovered ? "#332a45" : "#2a2438"
                    border.width: 1
                    border.color: page.line
                }
            }
        }
    }
}
