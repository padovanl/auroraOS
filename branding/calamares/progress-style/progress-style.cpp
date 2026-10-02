#include <QColor>
#include <QElapsedTimer>
#include <QProgressBar>
#include <QProxyStyle>
#include <QStylePlugin>
#include <QStringList>
#include <QTimer>

#include <algorithm>
#include <cmath>

class InstallerStyle : public QProxyStyle
{
public:
    InstallerStyle() : QProxyStyle(QStringLiteral("Fusion")) {}

    using QProxyStyle::polish;

    void polish(QWidget* widget) override
    {
        QProxyStyle::polish(widget);
        auto* bar = qobject_cast<QProgressBar*>(widget);
        if (!bar || bar->objectName() != QStringLiteral("exec-progress")
            || bar->findChild<QTimer*>(QStringLiteral("aurora-progress-animation")))
            return;

        auto* timer = new QTimer(bar);
        timer->setObjectName(QStringLiteral("aurora-progress-animation"));
        timer->setInterval(40);
        QElapsedTimer elapsed;
        elapsed.start();
        QObject::connect(timer, &QTimer::timeout, bar, [bar, elapsed]() {
            if (!bar->isVisible() || bar->window()->isMinimized()
                || bar->value() <= bar->minimum() || bar->value() >= bar->maximum())
                return;

            const double center = (elapsed.elapsed() % 2400) / 2400.0 * 1.5 - 0.25;
            QStringList stops;
            for (int index = 0; index <= 16; ++index) {
                const double position = index / 16.0;
                const double light = std::max(0.0, 1.0 - std::abs(position - center) / 0.18) * 0.48;
                const double red = 169 + (255 - 169) * position;
                const double green = 112 + (111 - 112) * position;
                const double blue = 255 + (145 - 255) * position;
                const QColor color(qRound(red + (255 - red) * light),
                                   qRound(green + (255 - green) * light),
                                   qRound(blue + (255 - blue) * light));
                stops.append(QStringLiteral("stop:%1 %2").arg(position).arg(color.name()));
            }
            bar->setStyleSheet(QStringLiteral(
                "QProgressBar::chunk { border-radius: 8px; "
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, %1); }")
                .arg(stops.join(QStringLiteral(", "))));
        });
        timer->start();
    }
};

class InstallerStylePlugin : public QStylePlugin
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QStyleFactoryInterface" FILE "progress-style.json")

public:
    QStyle* create(const QString& key) override
    {
        return key.compare(QStringLiteral("aurora-installer"), Qt::CaseInsensitive) == 0
            ? new InstallerStyle : nullptr;
    }
};

#include "progress-style.moc"