# Стили совпадают с RegCon для единообразия SAM-семейства
APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f0f2f5;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
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
QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
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
QLineEdit, QDateEdit, QComboBox {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 8px;
    background: #ffffff;
    min-height: 24px;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    text-align: center;
    height: 20px;
    background: #ffffff;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 4px;
}
QTextEdit#logView {
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 4px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QLabel#hintLabel {
    color: #64748b;
    font-size: 11px;
}
"""
