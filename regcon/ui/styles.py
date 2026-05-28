APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f0f2f5;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #1e293b;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 6px;
    padding: 6px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #334155;
}
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 6px 16px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #ffffff;
    font-weight: 600;
}
QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 500;
}
QPushButton:hover { background: #1d4ed8; }
QPushButton:pressed { background: #1e40af; }
QPushButton:disabled { background: #94a3b8; color: #e2e8f0; }
QPushButton#secondaryBtn {
    background: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
}
QPushButton#secondaryBtn:hover { background: #f8fafc; }
QPushButton#stopBtn {
    background: #dc2626;
}
QPushButton#stopBtn:hover { background: #b91c1c; }
QTableWidget {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    gridline-color: #f1f5f9;
    selection-background-color: #dbeafe;
}
QHeaderView::section {
    background: #f8fafc;
    padding: 5px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    text-align: center;
    height: 20px;
    background: #ffffff;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #2563eb);
    border-radius: 4px;
}
QComboBox, QLineEdit {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 8px;
    background: #ffffff;
}
QCheckBox { spacing: 6px; }
QTextEdit#logView {
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 4px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QLabel#progressLabel {
    font-weight: 600;
    color: #2563eb;
    min-width: 200px;
}
"""
