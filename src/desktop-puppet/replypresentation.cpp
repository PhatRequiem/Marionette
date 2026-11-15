#include "replypresentation.h"
#include <QColor>
#include <QFont>
#include <QTextBlock>
#include <QTextBoundaryFinder>
#include <QTextCursor>
#include <QTextDocumentFragment>

ReplyPresentation::ReplyPresentation(QObject *parent) : QObject(parent) {
    m_document.setUndoRedoEnabled(false);
    QFont font;
    font.setPixelSize(16);
    m_document.setDefaultFont(font);
    m_timer.setTimerType(Qt::PreciseTimer);
    m_timer.setInterval(8); // About 125 visible letters per second.
    connect(&m_timer, &QTimer::timeout, this, &ReplyPresentation::advance);
}

void ReplyPresentation::setMarkdown(const QString &markdown) {
    if (m_markdown == markdown) return;
    m_timer.stop();
    m_markdown = markdown;
    m_html.clear();
    m_boundaries.clear();
    m_next = 0;
    m_document.setMarkdown(markdown, QTextDocument::MarkdownFeatures(QTextDocument::MarkdownDialectGitHub) | QTextDocument::MarkdownNoHTML);
    // Keep image descriptions as text. No resource URLs reach the QML document.
    QList<QPair<int, QString>> images;
    for (auto block = m_document.begin(); block.isValid(); block = block.next()) {
        for (auto it = block.begin(); !it.atEnd(); ++it) {
            const auto fragment = it.fragment();
            if (fragment.charFormat().isImageFormat())
                for (int offset = 0; offset < fragment.length(); ++offset)
                    images.append({fragment.position() + offset, fragment.charFormat().stringProperty(QTextFormat::ImageAltText)});
        }
    }
    for (auto it = images.crbegin(); it != images.crend(); ++it) {
        QTextCursor cursor(&m_document);
        cursor.setPosition(it->first);
        cursor.movePosition(QTextCursor::NextCharacter, QTextCursor::KeepAnchor);
        cursor.insertText(it->second, QTextCharFormat());
    }
    // Keep paragraph breaks readable in the compact bubble; list items and
    // fenced code retain their tighter layout.
    for (auto block = m_document.begin(); block.isValid(); block = block.next()) {
        auto format = block.blockFormat();
        if (!block.textList() && !format.nonBreakableLines()) {
            format.setBottomMargin(8);
            QTextCursor(block).setBlockFormat(format);
        }
    }
    QTextCursor all(&m_document);
    all.select(QTextCursor::Document);
    QTextCharFormat color;
    color.setForeground(QColor("#FF4FA3")); // src/marionette/style.py: reply.
    all.mergeCharFormat(color);
    m_naturalWidth = m_document.idealWidth();
    const auto text = m_document.toRawText();
    QTextBoundaryFinder boundaries(QTextBoundaryFinder::Grapheme, text);
    for (auto end = boundaries.toNextBoundary(); end >= 0; end = boundaries.toNextBoundary())
        m_boundaries.append(int(end));
    emit sourceChanged();
    // Parse once before revealing, so Markdown punctuation never flashes and
    // combined accents/emoji appear as whole letters rather than broken UTF-16.
    advance();
    if (revealing()) m_timer.start();
}

void ReplyPresentation::advance() {
    if (revealing()) {
        QTextCursor prefix(&m_document);
        prefix.setPosition(m_boundaries.at(m_next++), QTextCursor::KeepAnchor);
        m_html = prefix.selection().toHtml();
    }
    if (!revealing()) m_timer.stop();
    emit changed();
}
