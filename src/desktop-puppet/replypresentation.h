#pragma once
#include <QObject>
#include <QTextDocument>
#include <QTimer>

// Message formatting never loads images, files or remote resources.
class ReplyDocument : public QTextDocument {
protected:
    QVariant loadResource(int, const QUrl &) override { return {}; }
};

class ReplyPresentation : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString markdown READ markdown WRITE setMarkdown NOTIFY sourceChanged)
    Q_PROPERTY(QString html READ html NOTIFY changed)
    Q_PROPERTY(qreal naturalWidth READ naturalWidth NOTIFY sourceChanged)
    Q_PROPERTY(bool revealing READ revealing NOTIFY changed)
public:
    explicit ReplyPresentation(QObject *parent = nullptr);
    QString markdown() const { return m_markdown; }
    QString html() const { return m_html; }
    qreal naturalWidth() const { return m_naturalWidth; }
    bool revealing() const { return m_next < m_boundaries.size(); }
    void setMarkdown(const QString &markdown);
signals:
    void sourceChanged();
    void changed();
private slots:
    void advance();
private:
    ReplyDocument m_document;
    QTimer m_timer;
    QString m_markdown, m_html;
    QList<int> m_boundaries;
    qsizetype m_next = 0;
    qreal m_naturalWidth = 0;
};
