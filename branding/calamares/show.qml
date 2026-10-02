/* Aurora OS installer slideshow (shown while files are copied).
   Texts follow the language chosen in the boot menu or the installer. */
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation

    // [heading, text] per slide, per language; English is the fallback.
    readonly property var texts: ({
        "en": [
            ["Welcome to Aurora OS", "A calm, fast desktop on the rock-solid Debian base. Sit back — this takes a few minutes."],
            ["Find anything with Super", "Apps, files, settings, quick math, unit and currency conversion, clipboard history and commands — all from one search."],
            ["Built for developers", "Git, compilers, Python, Node.js, containers and a modern terminal are ready. Dev Hub installs editors, languages and databases in one click."],
            ["A private AI assistant", "Chat, writing tools, dictation and read-aloud run on your computer, in your language. Nothing leaves it unless you choose a cloud service."],
            ["Make it yours", "Pick a layout, move the dock and panel, choose accent colors, fonts and a wallpaper that follows the time of day."],
            ["Play anything", "Game Hub sets up Steam with Proton, Epic and GOG, Windows programs and Android apps — each in one click."],
            ["Safe and healthy", "Security updates install by themselves, the firewall is on, a snapshot is taken before every update, and System Health keeps an eye on everything."]
        ],
        "it": [
            ["Benvenuto in Aurora OS", "Un desktop calmo e veloce sulla solida base di Debian. Mettiti comodo: ci vorrà qualche minuto."],
            ["Trova tutto con Super", "App, file, impostazioni, calcoli, conversioni di unità e valute, cronologia degli appunti e comandi: tutto da un'unica ricerca."],
            ["Pensato per sviluppatori", "Git, compilatori, Python, Node.js, container e un terminale moderno sono pronti. Dev Hub installa editor, linguaggi e database in un clic."],
            ["Un assistente IA privato", "Chat, strumenti di scrittura, dettatura e lettura ad alta voce funzionano sul tuo computer, nella tua lingua. Nulla esce, a meno che tu non scelga un servizio cloud."],
            ["Rendilo tuo", "Scegli un layout, sposta dock e barra, scegli colori, caratteri e uno sfondo che segue l'ora del giorno."],
            ["Gioca a tutto", "Game Hub configura Steam con Proton, Epic e GOG, programmi Windows e app Android: ognuno in un clic."],
            ["Sicuro e in salute", "Gli aggiornamenti di sicurezza si installano da soli, il firewall è attivo, prima di ogni aggiornamento viene creata un'istantanea e Stato del sistema tiene d'occhio tutto."]
        ],
        "es": [
            ["Bienvenido a Aurora OS", "Un escritorio tranquilo y rápido sobre la sólida base de Debian. Ponte cómodo: tardará unos minutos."],
            ["Encuentra todo con Super", "Aplicaciones, archivos, ajustes, cálculos, conversión de unidades y divisas, historial del portapapeles y comandos: todo en una búsqueda."],
            ["Hecho para desarrolladores", "Git, compiladores, Python, Node.js, contenedores y una terminal moderna ya están listos. Dev Hub instala editores, lenguajes y bases de datos en un clic."],
            ["Un asistente de IA privado", "Chat, herramientas de escritura, dictado y lectura en voz alta funcionan en tu equipo y en tu idioma. Nada sale de él salvo que elijas un servicio en la nube."],
            ["Hazlo tuyo", "Elige una disposición, mueve el dock y la barra, y elige colores, fuentes y un fondo que sigue la hora del día."],
            ["Juega a todo", "Game Hub configura Steam con Proton, Epic y GOG, programas de Windows y aplicaciones Android: cada uno en un clic."],
            ["Seguro y saludable", "Las actualizaciones de seguridad se instalan solas, el cortafuegos está activo, se crea una instantánea antes de cada actualización y Salud del sistema lo vigila todo."]
        ],
        "fr": [
            ["Bienvenue dans Aurora OS", "Un bureau calme et rapide sur la base solide de Debian. Installez-vous : cela prend quelques minutes."],
            ["Tout trouver avec Super", "Applications, fichiers, réglages, calculs, conversions d'unités et de devises, historique du presse-papiers et commandes : tout dans une seule recherche."],
            ["Pensé pour les développeurs", "Git, compilateurs, Python, Node.js, conteneurs et un terminal moderne sont prêts. Dev Hub installe éditeurs, langages et bases de données en un clic."],
            ["Un assistant IA privé", "Discussion, outils d'écriture, dictée et lecture à voix haute fonctionnent sur votre ordinateur, dans votre langue. Rien n'en sort, sauf si vous choisissez un service en ligne."],
            ["Faites-le vôtre", "Choisissez une disposition, déplacez le dock et la barre, choisissez couleurs, polices et un fond d'écran qui suit l'heure du jour."],
            ["Jouez à tout", "Game Hub installe Steam avec Proton, Epic et GOG, les programmes Windows et les applications Android, chacun en un clic."],
            ["Sûr et en bonne santé", "Les mises à jour de sécurité s'installent seules, le pare-feu est actif, un instantané est pris avant chaque mise à jour et Santé du système surveille tout."]
        ],
        "de": [
            ["Willkommen bei Aurora OS", "Ein ruhiger, schneller Desktop auf dem soliden Fundament von Debian. Lehn dich zurück – das dauert ein paar Minuten."],
            ["Alles finden mit Super", "Apps, Dateien, Einstellungen, Rechnen, Einheiten- und Währungsumrechnung, Zwischenablage-Verlauf und Befehle – alles in einer Suche."],
            ["Für Entwickler gemacht", "Git, Compiler, Python, Node.js, Container und ein modernes Terminal sind bereit. Dev Hub installiert Editoren, Sprachen und Datenbanken mit einem Klick."],
            ["Ein privater KI-Assistent", "Chat, Schreibwerkzeuge, Diktat und Vorlesen laufen auf deinem Rechner, in deiner Sprache. Nichts verlässt ihn, außer du wählst einen Cloud-Dienst."],
            ["Mach es zu deinem", "Wähle ein Layout, verschiebe Dock und Leiste, wähle Akzentfarben, Schriften und ein Hintergrundbild, das der Tageszeit folgt."],
            ["Spiel alles", "Game Hub richtet Steam mit Proton, Epic und GOG, Windows-Programme und Android-Apps ein – jeweils mit einem Klick."],
            ["Sicher und gesund", "Sicherheitsupdates installieren sich selbst, die Firewall ist an, vor jedem Update wird ein Schnappschuss erstellt und der Systemzustand behält alles im Blick."]
        ],
        "pt": [
            ["Bem-vindo ao Aurora OS", "Um desktop calmo e rápido sobre a base sólida do Debian. Relaxe: isso leva alguns minutos."],
            ["Encontre tudo com Super", "Aplicativos, arquivos, configurações, contas, conversão de unidades e moedas, histórico da área de transferência e comandos: tudo em uma busca."],
            ["Feito para desenvolvedores", "Git, compiladores, Python, Node.js, contêineres e um terminal moderno já vêm prontos. O Dev Hub instala editores, linguagens e bancos de dados em um clique."],
            ["Um assistente de IA privado", "Chat, ferramentas de escrita, ditado e leitura em voz alta rodam no seu computador, no seu idioma. Nada sai dele, a menos que você escolha um serviço na nuvem."],
            ["Deixe do seu jeito", "Escolha um layout, mova o dock e a barra, escolha cores, fontes e um papel de parede que acompanha a hora do dia."],
            ["Jogue de tudo", "O Game Hub configura o Steam com Proton, Epic e GOG, programas do Windows e apps Android: cada um em um clique."],
            ["Seguro e saudável", "As atualizações de segurança se instalam sozinhas, o firewall está ativo, um snapshot é criado antes de cada atualização e a Saúde do sistema vigia tudo."]
        ],
        "ru": [
            ["Добро пожаловать в Aurora OS", "Спокойный и быстрый рабочий стол на надёжной основе Debian. Устраивайтесь поудобнее — это займёт несколько минут."],
            ["Найдите всё клавишей Super", "Приложения, файлы, настройки, вычисления, перевод единиц и валют, история буфера обмена и команды — всё в одном поиске."],
            ["Создан для разработчиков", "Git, компиляторы, Python, Node.js, контейнеры и современный терминал уже готовы. Dev Hub устанавливает редакторы, языки и базы данных в один клик."],
            ["Личный ИИ-ассистент", "Чат, инструменты письма, диктовка и чтение вслух работают на вашем компьютере и на вашем языке. Ничего не уходит наружу, если вы не выберете облачный сервис."],
            ["Сделайте его своим", "Выберите макет, переместите док и панель, выберите цвета, шрифты и фон, меняющийся в течение дня."],
            ["Играйте во что угодно", "Game Hub настраивает Steam с Proton, Epic и GOG, программы Windows и приложения Android — каждое в один клик."],
            ["Безопасно и надёжно", "Обновления безопасности ставятся сами, брандмауэр включён, перед каждым обновлением делается снимок, а «Состояние системы» следит за всем."]
        ],
        "zh": [
            ["欢迎使用 Aurora OS", "基于稳如磐石的 Debian 打造的安静、快速的桌面。请稍候，这需要几分钟。"],
            ["按 Super 查找一切", "应用、文件、设置、快速计算、单位和货币换算、剪贴板历史和命令——一次搜索全部搞定。"],
            ["为开发者打造", "Git、编译器、Python、Node.js、容器和现代终端均已就绪。Dev Hub 一键安装编辑器、语言和数据库。"],
            ["私密的 AI 助手", "聊天、写作工具、语音输入和朗读都在你的电脑上以你的语言运行。除非你选择云服务，否则不会发送任何内容。"],
            ["打造你的专属桌面", "选择布局，移动程序坞和顶栏，挑选强调色、字体以及随时间变化的壁纸。"],
            ["畅玩一切", "Game Hub 一键配置 Steam 与 Proton、Epic 和 GOG、Windows 程序以及 Android 应用。"],
            ["安全又健康", "安全更新自动安装，防火墙已开启，每次更新前都会创建快照，“系统健康”时刻关注一切。"]
        ],
        "ja": [
            ["Aurora OS へようこそ", "堅牢な Debian をベースにした、静かで速いデスクトップ。数分かかりますので、少しお待ちください。"],
            ["Super キーで何でも検索", "アプリ、ファイル、設定、計算、単位と通貨の換算、クリップボード履歴、コマンドまで、ひとつの検索で。"],
            ["開発者のために", "Git、コンパイラー、Python、Node.js、コンテナ、モダンなターミナルがすぐ使えます。Dev Hub ならエディター、言語、データベースもワンクリック。"],
            ["プライベートな AI アシスタント", "チャット、文章ツール、音声入力、読み上げがあなたのコンピューター上で、あなたの言語で動きます。クラウドを選ばない限り何も送信されません。"],
            ["自分好みに", "レイアウトを選び、Dock とバーを動かし、アクセントカラー、フォント、時間とともに変わる壁紙を選べます。"],
            ["何でも遊べる", "Game Hub が Steam と Proton、Epic と GOG、Windows プログラム、Android アプリをそれぞれワンクリックで用意します。"],
            ["安全で健康", "セキュリティアップデートは自動でインストールされ、ファイアウォールは有効、アップデートのたびにスナップショットを作成し、システムの健康状態がすべてを見守ります。"]
        ],
        "ar": [
            ["مرحبًا بك في Aurora OS", "سطح مكتب هادئ وسريع على أساس Debian المتين. استرخِ، سيستغرق هذا بضع دقائق."],
            ["اعثر على أي شيء بمفتاح Super", "التطبيقات والملفات والإعدادات والحسابات وتحويل الوحدات والعملات وسجل الحافظة والأوامر، كلها في بحث واحد."],
            ["مصمَّم للمطورين", "Git والمترجمات وPython وNode.js والحاويات وطرفية حديثة جاهزة. يثبّت Dev Hub المحررات واللغات وقواعد البيانات بنقرة واحدة."],
            ["مساعد ذكاء اصطناعي خاص", "المحادثة وأدوات الكتابة والإملاء والقراءة بصوت عالٍ تعمل على حاسوبك وبلغتك. لا يغادره شيء إلا إذا اخترت خدمة سحابية."],
            ["اجعله خاصًا بك", "اختر تخطيطًا، وحرّك شريط التطبيقات والشريط العلوي، واختر الألوان والخطوط وخلفية تتبع وقت اليوم."],
            ["العب أي شيء", "يُعدّ Game Hub منصة Steam مع Proton وEpic وGOG وبرامج Windows وتطبيقات Android، كلٌّ بنقرة واحدة."],
            ["آمن وسليم", "تُثبَّت التحديثات الأمنية تلقائيًا، وجدار الحماية مفعّل، وتُلتقط لقطة قبل كل تحديث، وتراقب صحة النظام كل شيء."]
        ],
        "hi": [
            ["Aurora OS में आपका स्वागत है", "मज़बूत Debian पर बना एक शांत, तेज़ डेस्कटॉप। आराम से बैठिए, इसमें कुछ मिनट लगेंगे।"],
            ["Super से सब कुछ खोजें", "ऐप्स, फ़ाइलें, सेटिंग्स, गणना, इकाई और मुद्रा रूपांतरण, क्लिपबोर्ड इतिहास और कमांड — सब एक ही खोज में।"],
            ["डेवलपर्स के लिए बना", "Git, कंपाइलर, Python, Node.js, कंटेनर और एक आधुनिक टर्मिनल तैयार हैं। Dev Hub एक क्लिक में एडिटर, भाषाएँ और डेटाबेस स्थापित करता है।"],
            ["एक निजी AI सहायक", "चैट, लेखन उपकरण, डिक्टेशन और पढ़कर सुनाना आपके कंप्यूटर पर, आपकी भाषा में चलते हैं। जब तक आप क्लाउड सेवा न चुनें, कुछ भी बाहर नहीं जाता।"],
            ["इसे अपना बनाएँ", "एक लेआउट चुनें, डॉक और बार हटाएँ, एक्सेंट रंग, फ़ॉन्ट और दिन के समय के साथ बदलने वाली पृष्ठभूमि चुनें।"],
            ["कुछ भी खेलें", "Game Hub एक-एक क्लिक में Proton के साथ Steam, Epic और GOG, Windows प्रोग्राम और Android ऐप्स सेट करता है।"],
            ["सुरक्षित और स्वस्थ", "सुरक्षा अपडेट अपने-आप स्थापित होते हैं, फ़ायरवॉल चालू है, हर अपडेट से पहले स्नैपशॉट बनता है, और सिस्टम स्वास्थ्य सब पर नज़र रखता है।"]
        ]
    })
    readonly property var lang: {
        var code = Qt.locale().name.split("_")[0]
        return texts[code] !== undefined ? texts[code] : texts["en"]
    }
    readonly property var images: ["welcome", "spotlight", "developers", "ai", "yours", "games", "safe"]

    Timer {
        interval: 8000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    // Fill the whole slideshow area; Calamares otherwise shows its white base colour
    // around the slides.
    Rectangle {
        z: -1
        anchors.fill: parent
        clip: true
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1b1428" }
            GradientStop { position: 1.0; color: "#0d0a14" }
        }
        // Slow aurora glows drifting behind the slides.
        Repeater {
            model: [ { c: "#a970ff", x: 0.10, d: 11000 }, { c: "#35d0ba", x: 0.55, d: 14000 },
                     { c: "#ff6f91", x: 0.80, d: 17000 } ]
            Rectangle {
                width: parent.width * 0.55
                height: parent.height * 0.5
                radius: height / 2
                color: modelData.c
                opacity: 0.07
                y: -height * 0.35
                x: parent.width * modelData.x - width / 2
                SequentialAnimation on x {
                    loops: Animation.Infinite
                    running: presentation.activatedInCalamares
                    NumberAnimation { to: parent.width * modelData.x - width / 2 + 60; duration: modelData.d; easing.type: Easing.InOutSine }
                    NumberAnimation { to: parent.width * modelData.x - width / 2 - 60; duration: modelData.d; easing.type: Easing.InOutSine }
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: presentation.activatedInCalamares
                    NumberAnimation { to: 0.13; duration: modelData.d / 2; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.05; duration: modelData.d / 2; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    // A light that keeps sweeping along the bottom edge, right above the
    // installer's progress bar: the work goes on even when a step is long.
    Item {
        z: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 3
        clip: true
        Rectangle { anchors.fill: parent; color: "#a970ff"; opacity: 0.18 }
        Rectangle {
            id: sweep
            width: parent.width * 0.32
            height: parent.height
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.45; color: "#a970ff" }
                GradientStop { position: 0.75; color: "#ff6f91" }
                GradientStop { position: 1.0; color: "transparent" }
            }
            NumberAnimation on x {
                from: -sweep.width
                to: sweep.parent.width
                duration: 2400
                loops: Animation.Infinite
                easing.type: Easing.InOutQuad
                running: presentation.activatedInCalamares
            }
        }
    }

    component AuroraSlide: Slide {
        property int index: 0
        readonly property string heading: presentation.lang[index][0]
        readonly property string body: presentation.lang[index][1]

        // The default Slide geometry leaves margins; use the whole area.
        x: 0
        y: 0
        width: presentation.width
        height: presentation.height

        Text {
            id: headingText
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.05
            width: parent.width * 0.9
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: heading
            font.pixelSize: Math.max(20, parent.height * 0.055)
            font.weight: Font.DemiBold
            color: "#f2eefa"
        }
        Text {
            id: bodyText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: headingText.bottom
            anchors.topMargin: 8
            width: parent.width * 0.86
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: body
            font.pixelSize: Math.max(13, parent.height * 0.032)
            lineHeight: 1.2
            color: "#cfc7dd"
        }
        Rectangle {
            id: frame
            readonly property real maxW: parent.width * 0.86
            readonly property real maxH: parent.height - bodyText.y - bodyText.height - 36
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: bodyText.bottom
            anchors.topMargin: 18
            width: Math.max(0, Math.min(maxW, maxH * 16 / 9)) + 2
            height: width * 9 / 16
            radius: 6
            clip: true
            color: "#3a2f52"
            Image {
                anchors.fill: parent
                anchors.margins: 1
                source: "slides/" + presentation.images[index] + ".jpg"
                fillMode: Image.PreserveAspectFit
                smooth: true
                asynchronous: true
            }
        }
    }

    AuroraSlide { index: 0 }
    AuroraSlide { index: 1 }
    AuroraSlide { index: 2 }
    AuroraSlide { index: 3 }
    AuroraSlide { index: 4 }
    AuroraSlide { index: 5 }
    AuroraSlide { index: 6 }
}
