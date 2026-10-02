#include <QColor>
#include <QElapsedTimer>
#include <QEvent>
#include <QLayout>
#include <QPainterPath>
#include <QProgressBar>
#include <QProxyStyle>
#include <QQuickStyle>
#include <QRegion>
#include <QStylePlugin>
#include <QStringList>
#include <QTimer>

#include <algorithm>
#include <cmath>

class InstallerStyle : public QProxyStyle
{
public:
    InstallerStyle() : QProxyStyle(QStringLiteral("Fusion"))
    {
        QQuickStyle::setStyle(QStringLiteral("Fusion"));
    }

    using QProxyStyle::polish;

    void polish(QWidget* widget) override
    {
        QProxyStyle::polish(widget);
        if (widget->objectName() == QStringLiteral("qml")) {
            for (auto* parent = widget->parentWidget(); parent; parent = parent->parentWidget()) {
                if (parent->objectName() == QStringLiteral("slideshow")) {
                    widget->installEventFilter(this);
                    roundWidget(widget);
                    break;
                }
            }
        } else if (widget->objectName() == QStringLiteral("view-button-back")) {
            if (auto* navigation = widget->parentWidget(); navigation && navigation->layout()) {
                auto margins = navigation->layout()->contentsMargins();
                margins.setBottom(std::max(16, margins.bottom()));
                navigation->layout()->setContentsMargins(margins);
            }
        }
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

protected:
    bool eventFilter(QObject* watched, QEvent* event) override
    {
        if (event->type() == QEvent::Resize || event->type() == QEvent::Show) {
            if (auto* widget = qobject_cast<QWidget*>(watched))
                roundWidget(widget);
        }
        return QProxyStyle::eventFilter(watched, event);
    }

private:
    static void roundWidget(QWidget* widget)
    {
        QPainterPath outline;
        outline.addRoundedRect(QRectF(widget->rect()), 8, 8);
        widget->setMask(QRegion(outline.toFillPolygon().toPolygon()));
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