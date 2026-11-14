#include "backend.h"
#include <QRegion>
#include <QRectF>

void Backend::inputArea(qreal x, qreal y, qreal width, qreal height) {
    // The rest of the transparent layer must pass clicks to the desktop.
    if (m_window)
        m_window->setMask(QRegion(QRectF(x, y, width, height).toAlignedRect()));
}
