#include "backend.h"
#include <QRegion>
#include <QRectF>

void Backend::inputAreas(const QRectF &body, const QRectF &bubble) {
    // A wider reply must not intercept clicks in the empty space beside her.
    if (m_window)
        m_window->setMask(QRegion(body.toAlignedRect()) | QRegion(bubble.toAlignedRect()));
}
