#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py — lightweight, dependency-free localization for DisplayGuard.

English is the source language and the fallback for any missing key. The active
language is auto-detected from the Windows UI language on first run and can be
overridden by the user (persisted in config). Use t("key", **kwargs) everywhere.

To add a language: add its code to LANGUAGES and a dict to TRANSLATIONS. Any keys
you omit fall back to English automatically.
"""
from __future__ import annotations

from typing import Dict

# Display name shown in the language picker (native name), in menu order.
LANGUAGES: Dict[str, str] = {
    "en":      "English",
    "ko":      "한국어",
    "ja":      "日本語",
    "zh-Hans": "简体中文",
    "de":      "Deutsch",
    "es":      "Español",
    "fr":      "Français",
    "ru":      "Русский",
    "pt-BR":   "Português (BR)",
}

DEFAULT_LANG = "en"

# ─────────────────────────────────────────────────────────────────────────────
# Translation tables. Keys are stable identifiers; English is the source.
# {placeholders} are filled via str.format(**kwargs) in t().
# ─────────────────────────────────────────────────────────────────────────────
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "already_running_title": "DisplayGuard — Already running",
        "already_running_body":  "DisplayGuard is already running.\n\nClick the icon in the system tray (bottom-right),\nor check the taskbar.",
        "status_active":         "Protection active",
        "status_inactive":       "Protection disabled",
        "btn_disable":           "Disable protection",
        "btn_enable":            "Enable protection",
        "btn_save":              "Save current layout",
        "btn_restore_now":       "Restore now",
        "section_monitors":      "Saved reference layout",
        "col_monitor":           "Monitor",
        "col_position":          "Position",
        "col_resolution":        "Resolution",
        "col_refresh":           "Refresh",
        "section_log":           "Activity log",
        "footer_hint":           "Closing the window keeps it running in the tray  |  Click the tray icon to reopen",
        "tray_open":             "Open window",
        "tray_save":             "Save current layout",
        "tray_language":         "Language",
        "tray_exit":             "Exit",
        "status_short_active":   "active",
        "status_short_inactive": "inactive",
        "log_config_load_failed": "Failed to load settings: {error}",
        "log_config_save_failed": "Failed to save settings: {error}",
        "log_saved":             "Current layout saved ({count} monitors)",
        "log_no_saved":          "No saved layout",
        "log_restore_manual":    "Running manual restore...",
        "log_restore_done":      "Restore complete",
        "log_restore_error":     "Error during restore",
        "log_protection_on":     "Protection enabled",
        "log_protection_off":    "Protection disabled",
        "log_change_detected":   "Display change detected → auto-restore in {delay:.0f}s",
        "log_config_equal":      "Layout unchanged, no restore needed",
        "log_auto_restore_done": "Auto-restore complete",
        "log_auto_restore_error":"Error during auto-restore",
        "log_no_saved_autosave": "No saved layout → saving current layout automatically",
        "tray_started":          "[Tray] System tray icon started",
        "tray_missing_deps":     "[Warning] pystray/Pillow not installed → running without tray",
        "app_started":           "DisplayGuard v2.0 started — {count} monitors detected",
        "lang_changed":          "Language changed to {lang}",
    },
    "ko": {
        "already_running_title": "DisplayGuard - 이미 실행 중",
        "already_running_body":  "DisplayGuard가 이미 실행 중입니다.\n\n시스템 트레이(우측 하단)에서 아이콘을 클릭하거나\n작업 표시줄을 확인하세요.",
        "status_active":         "보호 활성 중",
        "status_inactive":       "보호 비활성화됨",
        "btn_disable":           "보호 비활성화",
        "btn_enable":            "보호 활성화",
        "btn_save":              "현재 설정 저장",
        "btn_restore_now":       "지금 복원",
        "section_monitors":      "저장된 모니터 기준 위치",
        "col_monitor":           "모니터",
        "col_position":          "위치",
        "col_resolution":        "해상도",
        "col_refresh":           "주사율",
        "section_log":           "활동 로그",
        "footer_hint":           "창을 닫아도 트레이에서 계속 실행됩니다  |  트레이 아이콘을 클릭하면 창이 다시 열립니다",
        "tray_open":             "창 열기",
        "tray_save":             "현재 설정 저장",
        "tray_language":         "언어",
        "tray_exit":             "종료",
        "status_short_active":   "활성",
        "status_short_inactive": "비활성",
        "log_config_load_failed": "설정 로드 실패: {error}",
        "log_config_save_failed": "설정 저장 실패: {error}",
        "log_saved":             "현재 설정 저장 완료 ({count}개 모니터)",
        "log_no_saved":          "저장된 설정 없음",
        "log_restore_manual":    "수동 복원 실행 중...",
        "log_restore_done":      "복원 완료",
        "log_restore_error":     "복원 중 오류 발생",
        "log_protection_on":     "보호 활성화",
        "log_protection_off":    "보호 비활성화",
        "log_change_detected":   "디스플레이 변경 감지 → {delay:.0f}초 후 자동 복원",
        "log_config_equal":      "설정 동일, 복원 불필요",
        "log_auto_restore_done": "자동 복원 완료",
        "log_auto_restore_error":"자동 복원 중 오류",
        "log_no_saved_autosave": "저장된 설정 없음 → 현재 설정 자동 저장",
        "tray_started":          "[트레이] 시스템 트레이 아이콘 시작",
        "tray_missing_deps":     "[경고] pystray/Pillow 미설치 → 트레이 없이 실행",
        "app_started":           "DisplayGuard v2.0 시작 — {count}개 모니터 감지",
        "lang_changed":          "언어가 {lang}(으)로 변경됨",
    },
    "ja": {
        "already_running_title": "DisplayGuard - 既に実行中",
        "already_running_body":  "DisplayGuard は既に実行中です。\n\n通知領域（右下）のアイコンをクリックするか、\nタスクバーをご確認ください。",
        "status_active":         "保護が有効",
        "status_inactive":       "保護が無効",
        "btn_disable":           "保護を無効化",
        "btn_enable":            "保護を有効化",
        "btn_save":              "現在の配置を保存",
        "btn_restore_now":       "今すぐ復元",
        "section_monitors":      "保存された基準配置",
        "col_monitor":           "モニター",
        "col_position":          "位置",
        "col_resolution":        "解像度",
        "col_refresh":           "リフレッシュ",
        "section_log":           "アクティビティログ",
        "footer_hint":           "ウィンドウを閉じても通知領域で動作し続けます  |  アイコンをクリックすると再表示します",
        "tray_open":             "ウィンドウを開く",
        "tray_save":             "現在の配置を保存",
        "tray_language":         "言語",
        "tray_exit":             "終了",
        "status_short_active":   "有効",
        "status_short_inactive": "無効",
        "log_config_load_failed": "設定の読み込みに失敗: {error}",
        "log_config_save_failed": "設定の保存に失敗: {error}",
        "log_saved":             "現在の配置を保存しました（{count} 台）",
        "log_no_saved":          "保存された配置がありません",
        "log_restore_manual":    "手動復元を実行中...",
        "log_restore_done":      "復元が完了しました",
        "log_restore_error":     "復元中にエラーが発生しました",
        "log_protection_on":     "保護を有効化しました",
        "log_protection_off":    "保護を無効化しました",
        "log_change_detected":   "ディスプレイ変更を検出 → {delay:.0f} 秒後に自動復元",
        "log_config_equal":      "配置に変更なし、復元は不要です",
        "log_auto_restore_done": "自動復元が完了しました",
        "log_auto_restore_error":"自動復元中にエラーが発生しました",
        "log_no_saved_autosave": "保存された配置がありません → 現在の配置を自動保存",
        "tray_started":          "[トレイ] 通知領域アイコンを開始しました",
        "tray_missing_deps":     "[警告] pystray/Pillow が未インストール → トレイなしで実行",
        "app_started":           "DisplayGuard v2.0 を起動 — {count} 台のモニターを検出",
        "lang_changed":          "言語を {lang} に変更しました",
    },
    "zh-Hans": {
        "already_running_title": "DisplayGuard - 已在运行",
        "already_running_body":  "DisplayGuard 已在运行。\n\n请点击系统托盘（右下角）中的图标，\n或查看任务栏。",
        "status_active":         "保护已启用",
        "status_inactive":       "保护已禁用",
        "btn_disable":           "禁用保护",
        "btn_enable":            "启用保护",
        "btn_save":              "保存当前布局",
        "btn_restore_now":       "立即恢复",
        "section_monitors":      "已保存的参考布局",
        "col_monitor":           "显示器",
        "col_position":          "位置",
        "col_resolution":        "分辨率",
        "col_refresh":           "刷新率",
        "section_log":           "活动日志",
        "footer_hint":           "关闭窗口后仍会在托盘中运行  |  点击托盘图标可重新打开",
        "tray_open":             "打开窗口",
        "tray_save":             "保存当前布局",
        "tray_language":         "语言",
        "tray_exit":             "退出",
        "status_short_active":   "启用",
        "status_short_inactive": "禁用",
        "log_config_load_failed": "加载设置失败：{error}",
        "log_config_save_failed": "保存设置失败：{error}",
        "log_saved":             "已保存当前布局（{count} 台显示器）",
        "log_no_saved":          "没有已保存的布局",
        "log_restore_manual":    "正在手动恢复...",
        "log_restore_done":      "恢复完成",
        "log_restore_error":     "恢复时出错",
        "log_protection_on":     "保护已启用",
        "log_protection_off":    "保护已禁用",
        "log_change_detected":   "检测到显示器变化 → {delay:.0f} 秒后自动恢复",
        "log_config_equal":      "布局未变化，无需恢复",
        "log_auto_restore_done": "自动恢复完成",
        "log_auto_restore_error":"自动恢复时出错",
        "log_no_saved_autosave": "没有已保存的布局 → 自动保存当前布局",
        "tray_started":          "[托盘] 系统托盘图标已启动",
        "tray_missing_deps":     "[警告] 未安装 pystray/Pillow → 在无托盘模式下运行",
        "app_started":           "DisplayGuard v2.0 已启动 — 检测到 {count} 台显示器",
        "lang_changed":          "语言已更改为 {lang}",
    },
    "de": {
        "already_running_title": "DisplayGuard – Läuft bereits",
        "already_running_body":  "DisplayGuard läuft bereits.\n\nKlicken Sie auf das Symbol im Infobereich (unten rechts)\noder prüfen Sie die Taskleiste.",
        "status_active":         "Schutz aktiv",
        "status_inactive":       "Schutz deaktiviert",
        "btn_disable":           "Schutz deaktivieren",
        "btn_enable":            "Schutz aktivieren",
        "btn_save":              "Aktuelles Layout speichern",
        "btn_restore_now":       "Jetzt wiederherstellen",
        "section_monitors":      "Gespeichertes Referenz-Layout",
        "col_monitor":           "Monitor",
        "col_position":          "Position",
        "col_resolution":        "Auflösung",
        "col_refresh":           "Frequenz",
        "section_log":           "Aktivitätsprotokoll",
        "footer_hint":           "Beim Schließen läuft es im Infobereich weiter  |  Klicken Sie auf das Symbol, um es erneut zu öffnen",
        "tray_open":             "Fenster öffnen",
        "tray_save":             "Aktuelles Layout speichern",
        "tray_language":         "Sprache",
        "tray_exit":             "Beenden",
        "status_short_active":   "aktiv",
        "status_short_inactive": "inaktiv",
        "log_config_load_failed": "Einstellungen konnten nicht geladen werden: {error}",
        "log_config_save_failed": "Einstellungen konnten nicht gespeichert werden: {error}",
        "log_saved":             "Aktuelles Layout gespeichert ({count} Monitore)",
        "log_no_saved":          "Kein gespeichertes Layout",
        "log_restore_manual":    "Manuelle Wiederherstellung läuft...",
        "log_restore_done":      "Wiederherstellung abgeschlossen",
        "log_restore_error":     "Fehler bei der Wiederherstellung",
        "log_protection_on":     "Schutz aktiviert",
        "log_protection_off":    "Schutz deaktiviert",
        "log_change_detected":   "Anzeigeänderung erkannt → automatische Wiederherstellung in {delay:.0f}s",
        "log_config_equal":      "Layout unverändert, keine Wiederherstellung nötig",
        "log_auto_restore_done": "Automatische Wiederherstellung abgeschlossen",
        "log_auto_restore_error":"Fehler bei der automatischen Wiederherstellung",
        "log_no_saved_autosave": "Kein gespeichertes Layout → aktuelles Layout wird automatisch gespeichert",
        "tray_started":          "[Infobereich] Symbol gestartet",
        "tray_missing_deps":     "[Warnung] pystray/Pillow nicht installiert → Ausführung ohne Infobereich",
        "app_started":           "DisplayGuard v2.0 gestartet — {count} Monitore erkannt",
        "lang_changed":          "Sprache geändert zu {lang}",
    },
    "es": {
        "already_running_title": "DisplayGuard: ya está en ejecución",
        "already_running_body":  "DisplayGuard ya se está ejecutando.\n\nHaz clic en el icono de la bandeja del sistema (abajo a la derecha)\no revisa la barra de tareas.",
        "status_active":         "Protección activa",
        "status_inactive":       "Protección desactivada",
        "btn_disable":           "Desactivar protección",
        "btn_enable":            "Activar protección",
        "btn_save":              "Guardar disposición actual",
        "btn_restore_now":       "Restaurar ahora",
        "section_monitors":      "Disposición de referencia guardada",
        "col_monitor":           "Monitor",
        "col_position":          "Posición",
        "col_resolution":        "Resolución",
        "col_refresh":           "Frecuencia",
        "section_log":           "Registro de actividad",
        "footer_hint":           "Al cerrar la ventana sigue en la bandeja  |  Haz clic en el icono para volver a abrirla",
        "tray_open":             "Abrir ventana",
        "tray_save":             "Guardar disposición actual",
        "tray_language":         "Idioma",
        "tray_exit":             "Salir",
        "status_short_active":   "activa",
        "status_short_inactive": "inactiva",
        "log_config_load_failed": "Error al cargar la configuración: {error}",
        "log_config_save_failed": "Error al guardar la configuración: {error}",
        "log_saved":             "Disposición actual guardada ({count} monitores)",
        "log_no_saved":          "No hay disposición guardada",
        "log_restore_manual":    "Restaurando manualmente...",
        "log_restore_done":      "Restauración completada",
        "log_restore_error":     "Error durante la restauración",
        "log_protection_on":     "Protección activada",
        "log_protection_off":    "Protección desactivada",
        "log_change_detected":   "Cambio de pantalla detectado → restauración automática en {delay:.0f}s",
        "log_config_equal":      "Disposición sin cambios, no es necesario restaurar",
        "log_auto_restore_done": "Restauración automática completada",
        "log_auto_restore_error":"Error durante la restauración automática",
        "log_no_saved_autosave": "No hay disposición guardada → guardando la actual automáticamente",
        "tray_started":          "[Bandeja] Icono de la bandeja iniciado",
        "tray_missing_deps":     "[Advertencia] pystray/Pillow no instalado → ejecutando sin bandeja",
        "app_started":           "DisplayGuard v2.0 iniciado: {count} monitores detectados",
        "lang_changed":          "Idioma cambiado a {lang}",
    },
    "fr": {
        "already_running_title": "DisplayGuard — Déjà en cours d'exécution",
        "already_running_body":  "DisplayGuard est déjà en cours d'exécution.\n\nCliquez sur l'icône dans la zone de notification (en bas à droite)\nou vérifiez la barre des tâches.",
        "status_active":         "Protection active",
        "status_inactive":       "Protection désactivée",
        "btn_disable":           "Désactiver la protection",
        "btn_enable":            "Activer la protection",
        "btn_save":              "Enregistrer la disposition actuelle",
        "btn_restore_now":       "Restaurer maintenant",
        "section_monitors":      "Disposition de référence enregistrée",
        "col_monitor":           "Écran",
        "col_position":          "Position",
        "col_resolution":        "Résolution",
        "col_refresh":           "Fréquence",
        "section_log":           "Journal d'activité",
        "footer_hint":           "Fermer la fenêtre la maintient dans la zone de notification  |  Cliquez sur l'icône pour la rouvrir",
        "tray_open":             "Ouvrir la fenêtre",
        "tray_save":             "Enregistrer la disposition actuelle",
        "tray_language":         "Langue",
        "tray_exit":             "Quitter",
        "status_short_active":   "active",
        "status_short_inactive": "inactive",
        "log_config_load_failed": "Échec du chargement des paramètres : {error}",
        "log_config_save_failed": "Échec de l'enregistrement des paramètres : {error}",
        "log_saved":             "Disposition actuelle enregistrée ({count} écrans)",
        "log_no_saved":          "Aucune disposition enregistrée",
        "log_restore_manual":    "Restauration manuelle en cours...",
        "log_restore_done":      "Restauration terminée",
        "log_restore_error":     "Erreur lors de la restauration",
        "log_protection_on":     "Protection activée",
        "log_protection_off":    "Protection désactivée",
        "log_change_detected":   "Changement d'affichage détecté → restauration automatique dans {delay:.0f}s",
        "log_config_equal":      "Disposition inchangée, restauration inutile",
        "log_auto_restore_done": "Restauration automatique terminée",
        "log_auto_restore_error":"Erreur lors de la restauration automatique",
        "log_no_saved_autosave": "Aucune disposition enregistrée → enregistrement automatique de l'actuelle",
        "tray_started":          "[Zone de notification] Icône démarrée",
        "tray_missing_deps":     "[Avertissement] pystray/Pillow non installé → exécution sans icône",
        "app_started":           "DisplayGuard v2.0 démarré — {count} écrans détectés",
        "lang_changed":          "Langue changée en {lang}",
    },
    "ru": {
        "already_running_title": "DisplayGuard — уже запущен",
        "already_running_body":  "DisplayGuard уже запущен.\n\nЩёлкните значок в области уведомлений (справа внизу)\nили проверьте панель задач.",
        "status_active":         "Защита включена",
        "status_inactive":       "Защита отключена",
        "btn_disable":           "Отключить защиту",
        "btn_enable":            "Включить защиту",
        "btn_save":              "Сохранить текущую раскладку",
        "btn_restore_now":       "Восстановить сейчас",
        "section_monitors":      "Сохранённая эталонная раскладка",
        "col_monitor":           "Монитор",
        "col_position":          "Положение",
        "col_resolution":        "Разрешение",
        "col_refresh":           "Частота",
        "section_log":           "Журнал действий",
        "footer_hint":           "При закрытии окна работа продолжается в трее  |  Щёлкните значок, чтобы открыть снова",
        "tray_open":             "Открыть окно",
        "tray_save":             "Сохранить текущую раскладку",
        "tray_language":         "Язык",
        "tray_exit":             "Выход",
        "status_short_active":   "вкл",
        "status_short_inactive": "выкл",
        "log_config_load_failed": "Не удалось загрузить настройки: {error}",
        "log_config_save_failed": "Не удалось сохранить настройки: {error}",
        "log_saved":             "Текущая раскладка сохранена ({count} мониторов)",
        "log_no_saved":          "Нет сохранённой раскладки",
        "log_restore_manual":    "Выполняется ручное восстановление...",
        "log_restore_done":      "Восстановление завершено",
        "log_restore_error":     "Ошибка при восстановлении",
        "log_protection_on":     "Защита включена",
        "log_protection_off":    "Защита отключена",
        "log_change_detected":   "Обнаружено изменение дисплея → автовосстановление через {delay:.0f} с",
        "log_config_equal":      "Раскладка не изменилась, восстановление не требуется",
        "log_auto_restore_done": "Автовосстановление завершено",
        "log_auto_restore_error":"Ошибка при автовосстановлении",
        "log_no_saved_autosave": "Нет сохранённой раскладки → текущая сохраняется автоматически",
        "tray_started":          "[Трей] Значок в области уведомлений запущен",
        "tray_missing_deps":     "[Предупреждение] pystray/Pillow не установлены → запуск без трея",
        "app_started":           "DisplayGuard v2.0 запущен — обнаружено мониторов: {count}",
        "lang_changed":          "Язык изменён на {lang}",
    },
    "pt-BR": {
        "already_running_title": "DisplayGuard — Já está em execução",
        "already_running_body":  "O DisplayGuard já está em execução.\n\nClique no ícone na bandeja do sistema (canto inferior direito)\nou verifique a barra de tarefas.",
        "status_active":         "Proteção ativa",
        "status_inactive":       "Proteção desativada",
        "btn_disable":           "Desativar proteção",
        "btn_enable":            "Ativar proteção",
        "btn_save":              "Salvar layout atual",
        "btn_restore_now":       "Restaurar agora",
        "section_monitors":      "Layout de referência salvo",
        "col_monitor":           "Monitor",
        "col_position":          "Posição",
        "col_resolution":        "Resolução",
        "col_refresh":           "Atualização",
        "section_log":           "Registro de atividades",
        "footer_hint":           "Fechar a janela mantém o app na bandeja  |  Clique no ícone para reabrir",
        "tray_open":             "Abrir janela",
        "tray_save":             "Salvar layout atual",
        "tray_language":         "Idioma",
        "tray_exit":             "Sair",
        "status_short_active":   "ativa",
        "status_short_inactive": "inativa",
        "log_config_load_failed": "Falha ao carregar as configurações: {error}",
        "log_config_save_failed": "Falha ao salvar as configurações: {error}",
        "log_saved":             "Layout atual salvo ({count} monitores)",
        "log_no_saved":          "Nenhum layout salvo",
        "log_restore_manual":    "Executando restauração manual...",
        "log_restore_done":      "Restauração concluída",
        "log_restore_error":     "Erro durante a restauração",
        "log_protection_on":     "Proteção ativada",
        "log_protection_off":    "Proteção desativada",
        "log_change_detected":   "Alteração de tela detectada → restauração automática em {delay:.0f}s",
        "log_config_equal":      "Layout inalterado, restauração desnecessária",
        "log_auto_restore_done": "Restauração automática concluída",
        "log_auto_restore_error":"Erro durante a restauração automática",
        "log_no_saved_autosave": "Nenhum layout salvo → salvando o atual automaticamente",
        "tray_started":          "[Bandeja] Ícone da bandeja iniciado",
        "tray_missing_deps":     "[Aviso] pystray/Pillow não instalado → executando sem bandeja",
        "app_started":           "DisplayGuard v2.0 iniciado — {count} monitores detectados",
        "lang_changed":          "Idioma alterado para {lang}",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# State + API
# ─────────────────────────────────────────────────────────────────────────────

_current = DEFAULT_LANG


def detect_system_language() -> str:
    """Best-effort detection of the Windows UI language → one of LANGUAGES."""
    primary = None
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = langid & 0x3FF
    except Exception:
        primary = None

    # Windows primary language id → our code.
    by_primary = {
        0x09: "en", 0x12: "ko", 0x11: "ja", 0x04: "zh-Hans",
        0x07: "de", 0x0A: "es", 0x0C: "fr", 0x19: "ru", 0x16: "pt-BR",
    }
    if primary in by_primary:
        return by_primary[primary]

    # Fallback: standard locale string like "ko_KR".
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    if loc.startswith("ko"):
        return "ko"
    if loc.startswith("ja"):
        return "ja"
    if loc.startswith("zh"):
        return "zh-Hans"
    if loc.startswith("de"):
        return "de"
    if loc.startswith("es"):
        return "es"
    if loc.startswith("fr"):
        return "fr"
    if loc.startswith("ru"):
        return "ru"
    if loc.startswith("pt"):
        return "pt-BR"
    return DEFAULT_LANG


def set_language(code: str) -> None:
    global _current
    if code in TRANSLATIONS:
        _current = code
    else:
        _current = DEFAULT_LANG


def get_language() -> str:
    return _current


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def t(key: str, **kwargs) -> str:
    """Translate `key` for the active language, falling back to English, then to
    the key itself. {placeholders} are filled from kwargs."""
    table = TRANSLATIONS.get(_current, {})
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANG].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
