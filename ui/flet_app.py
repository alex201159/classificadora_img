from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import flet as ft

from app.cap_catalog import CapCatalog, CatalogError
from app.config import MachineConfig, OutputConfig
from app.controller import MachineController
from app.production_pipeline import PipelineResult, ProductionPipeline
from app.settings_store import MachineSettingsStore, SettingsError
from camera.capture import CameraDetector
from camera.stream import CameraStream
from vision.reference_classifier import ClassificationResult, ReferenceImageClassifier
from vision.roi import RoiError, resolve_roi
from vision.tracker import TrackedCap


INK = "#101828"
SURFACE = "#FFFFFF"
BACKGROUND = "#F2F4F7"
GREEN = "#087A67"
GREEN_SOFT = "#EAF7F3"
RED = "#B42318"
RED_SOFT = "#FEF3F2"
AMBER = "#F79009"
MUTED = "#667085"
BORDER = "#D0D5DD"
SUBTLE = "#F8FAFB"
HEADER = "#101828"


class FletMachineApp:
    def __init__(
        self,
        page: ft.Page,
        controller: MachineController,
        config: MachineConfig,
        camera: CameraStream,
        config_path: str | Path,
    ) -> None:
        self.page = page
        self.controller = controller
        self.config = config
        self.settings_store = MachineSettingsStore(config_path)
        self.catalog = CapCatalog(config.interface.catalog_file, config.interface.images_dir)
        recognition = config.recognition
        self.classifier = ReferenceImageClassifier(
            self.catalog,
            ratio_threshold=recognition.ratio_threshold,
            min_good_matches=recognition.min_good_matches,
            min_inliers=recognition.min_inliers,
            ambiguity_ratio=recognition.ambiguity_ratio,
            max_image_width=recognition.max_image_width,
            sift_features=recognition.sift_features,
            flann_checks=recognition.flann_checks,
            color_weight=recognition.color_weight,
            color_candidate_margin=recognition.color_candidate_margin,
            max_color_references_per_class=recognition.max_color_references_per_class,
            min_color_similarity=recognition.min_color_similarity,
            max_elongation_ratio=recognition.max_elongation_ratio,
        )
        self.pipeline = ProductionPipeline(
            config,
            controller,
            self.classifier,
            self._output_for_class,
        )
        self.presence_detector = self.pipeline.presence_detector
        self.camera = camera
        self._log = logging.getLogger(__name__)
        self._active = True
        self._current_frame: Any | None = None
        self._selected_class_id: str | None = None
        self._last_scan = 0.0
        self._last_display = 0.0
        self._active_tracks: list[TrackedCap] = []
        self._last_result = ClassificationResult(None, "AGUARDANDO", 0.0, 0, 0, False)
        self._last_latency_ms = 0.0
        self._current_view_index = 0

        self.camera_image = ft.Image(
            src=self._placeholder_image(),
            fit=ft.BoxFit.CONTAIN,
            gapless_playback=True,
            filter_quality=ft.FilterQuality.LOW,
            expand=True,
        )
        self.machine_badge = ft.Text("PARADO", color=SURFACE, weight=ft.FontWeight.BOLD, size=12)
        self.machine_status_icon = ft.Icon(ft.Icons.CIRCLE, color="#98A2B3", size=9)
        self.machine_badge_container = ft.Container(
            ft.Row([self.machine_status_icon, self.machine_badge], spacing=7),
            bgcolor="#344054",
            border=ft.Border.all(1, "#475467"),
            padding=ft.Padding.symmetric(horizontal=11, vertical=7),
            border_radius=4,
        )
        self.camera_badge = ft.Text("ABRINDO CAMERA", color=AMBER, weight=ft.FontWeight.BOLD, size=11)
        self.result_name = ft.Text(
            "AGUARDANDO",
            color=INK,
            size=28,
            weight=ft.FontWeight.BOLD,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.result_detail = ft.Text("0% DE CONFIANCA", color=MUTED, size=11, weight=ft.FontWeight.BOLD)
        self.confidence_bar = ft.ProgressBar(value=0, color=GREEN, bgcolor="#E4E7EC", bar_height=7)
        self.total_count = ft.Text("0", size=34, weight=ft.FontWeight.BOLD, color=INK)
        self.class_counters = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.conveyor_state = ft.Text("ESTEIRA PARADA", color=MUTED, weight=ft.FontWeight.BOLD, size=11)
        self.ejection_state = ft.Text("0 JATOS", color=MUTED, weight=ft.FontWeight.BOLD, size=11)
        self.manual_eject_button = ft.Button(
            "TESTAR JATO",
            icon=ft.Icons.AIR,
            bgcolor="#344054",
            color=SURFACE,
            height=40,
            on_click=self._manual_eject,
            style=self._button_style(),
        )
        self.start_button = ft.Button(
            "INICIAR",
            icon=ft.Icons.PLAY_ARROW,
            bgcolor=GREEN,
            color=SURFACE,
            height=50,
            expand=True,
            on_click=self._start,
            style=self._button_style(),
        )
        self.stop_button = ft.Button(
            "PARAR",
            icon=ft.Icons.STOP,
            bgcolor=RED,
            color=SURFACE,
            height=50,
            expand=True,
            disabled=True,
            on_click=self._stop,
            style=self._button_style(),
        )
        self.calibrate_button = ft.Button(
            "CALIBRAR FUNDO",
            icon=ft.Icons.CENTER_FOCUS_STRONG,
            bgcolor="#344054",
            color=SURFACE,
            height=46,
            on_click=self._calibrate_background,
            style=self._button_style(),
        )
        self.notice = ft.Text("", color=MUTED, size=11, max_lines=2)

        self.name_field = ft.TextField(label="Nome da tampa", max_length=60, dense=True)
        self.color_field = ft.Dropdown(
            label="Cor",
            value="vermelha",
            dense=True,
            options=[
                ft.DropdownOption(key=value, text=label)
                for value, label in [
                    ("vermelha", "Vermelha"),
                    ("azul", "Azul"),
                    ("verde", "Verde"),
                    ("amarela", "Amarela"),
                    ("branca", "Branca"),
                    ("preta", "Preta"),
                    ("outra", "Outra"),
                ]
            ],
        )
        self.shape_field = ft.Dropdown(
            label="Formato",
            value="redonda",
            dense=True,
            options=[
                ft.DropdownOption(key=value, text=label)
                for value, label in [
                    ("redonda", "Redonda"),
                    ("quadrada", "Quadrada"),
                    ("oval", "Oval"),
                    ("outro", "Outro"),
                ]
            ],
        )
        self.output_field = ft.Dropdown(
            label="Saida",
            value=next(iter(config.outputs)),
            dense=True,
            options=[
                ft.DropdownOption(key=name, text=name.replace("_", " ").upper())
                for name in config.outputs
            ],
        )
        self.class_selector = ft.Dropdown(
            label="Classe para captura",
            dense=True,
            on_select=self._select_class,
        )
        self.rename_field = ft.TextField(
            label="Novo nome da classe",
            max_length=60,
            dense=True,
            disabled=True,
            expand=True,
        )
        self.rename_button = ft.Button(
            "RENOMEAR",
            icon=ft.Icons.EDIT,
            bgcolor="#344054",
            color=SURFACE,
            height=44,
            disabled=True,
            on_click=self._rename_class,
            style=self._button_style(),
        )
        self.class_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.samples_badge = ft.Text(
            "0 AMOSTRAS",
            color=MUTED,
            size=11,
            weight=ft.FontWeight.BOLD,
        )

        resolution_value = f"{config.camera.width}x{config.camera.height}"
        resolutions = ["640x480", "1280x720", "1920x1080"]
        if resolution_value not in resolutions:
            resolutions.append(resolution_value)
        self.machine_name_field = ft.TextField(
            label="Nome da maquina",
            value=config.name,
            dense=True,
            max_length=80,
        )
        self.camera_device_field = ft.Dropdown(
            label="Camera USB",
            value=str(config.camera.device),
            dense=True,
            expand=True,
            options=[
                ft.DropdownOption(
                    key=str(config.camera.device),
                    text=f"Dispositivo {config.camera.device} (em uso)",
                )
            ],
        )
        self.scan_cameras_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_color=GREEN,
            tooltip="Procurar cameras USB",
            on_click=self._scan_cameras,
        )
        self.camera_resolution_field = ft.Dropdown(
            label="Resolucao",
            value=resolution_value,
            dense=True,
            width=180,
            options=[ft.DropdownOption(key=value, text=value.replace("x", " x ")) for value in resolutions],
        )
        self.camera_fps_field = ft.Dropdown(
            label="Quadros por segundo",
            value=str(config.camera.fps),
            dense=True,
            width=170,
            options=[ft.DropdownOption(key=str(value), text=f"{value} FPS") for value in [15, 30, 60]],
        )
        self.conveyor_speed_field = ft.TextField(
            label="Velocidade da esteira (mm/s)",
            value=self._format_number(config.conveyor.speed_mm_s),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.min_matches_field = ft.TextField(
            label="Correspondencias minimas",
            value=str(config.recognition.min_good_matches),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.min_inliers_field = ft.TextField(
            label="Pontos geometricos minimos",
            value=str(config.recognition.min_inliers),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.scan_interval_field = ft.TextField(
            label="Intervalo de analise (ms)",
            value=str(config.recognition.scan_interval_ms),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.processing_width_field = ft.TextField(
            label="Largura de processamento (px)",
            value=str(config.recognition.max_image_width),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.stable_hits_field = ft.TextField(
            label="Confirmacoes por tampa",
            value=str(config.recognition.stable_hits),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.background_threshold_field = ft.TextField(
            label="Sensibilidade do fundo",
            value=str(config.recognition.background_threshold),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        self.presence_area_field = ft.TextField(
            label="Area minima de presenca (%)",
            value=self._format_number(config.recognition.min_foreground_ratio * 100),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.color_weight_field = ft.TextField(
            label="Peso da cor (%)",
            value=self._format_number(config.recognition.color_weight * 100),
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.machine_settings_notice = ft.Text("", color=MUTED, size=11, max_lines=2)
        self.save_machine_button = ft.Button(
            "SALVAR CONFIGURACAO",
            icon=ft.Icons.SAVE,
            bgcolor=GREEN,
            color=SURFACE,
            height=44,
            on_click=self._save_machine_settings,
            style=self._button_style(),
        )

        self.outputs_list = ft.Column(spacing=8)
        self.settings_notice = ft.Text("", color=MUTED, size=11, max_lines=2)
        self.new_output_name = ft.TextField(
            label="Nome da nova saida",
            hint_text="ex.: azul",
            dense=True,
            width=220,
        )
        self.new_output_gpio = ft.TextField(
            label="GPIO wPi",
            hint_text="ex.: 21",
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=130,
        )
        self.new_output_delay = ft.TextField(
            label="Atraso (ms)",
            value="1500",
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
        )
        self.new_output_pulse = ft.TextField(
            label="Pulso (ms)",
            value="100",
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=130,
        )
        self.new_output_active_high = ft.Switch(label="Ativo em nivel alto", value=True)

        self.view_context = ft.Text(
            "PRODUCAO  /  MONITORAMENTO",
            color=MUTED,
            size=10,
            weight=ft.FontWeight.BOLD,
        )
        self.view_title = ft.Text(
            "Operacao",
            color=INK,
            size=22,
            weight=ft.FontWeight.BOLD,
        )
        self.machine_name_display = ft.Text(
            config.name.upper(), color=MUTED, size=10, weight=ft.FontWeight.BOLD
        )
        self.sidebar_machine_status = ft.Text(
            "PARADA SEGURA", color="#D0D5DD", size=11, weight=ft.FontWeight.BOLD
        )
        self.sidebar_camera_status = ft.Text(
            "INICIALIZANDO", color="#D0D5DD", size=11, weight=ft.FontWeight.BOLD
        )
        self.sidebar_catalog_status = ft.Text(
            "0 AMOSTRAS", color="#D0D5DD", size=11, weight=ft.FontWeight.BOLD
        )
        self.footer_output_status = ft.Text(
            f"SAIDAS: {len(config.outputs)}",
            color=MUTED,
            size=10,
            weight=ft.FontWeight.BOLD,
        )
        self.footer_safety_status = ft.Text(
            "ESTADO SEGURO", color=MUTED, size=10, weight=ft.FontWeight.BOLD
        )
        self.footer_camera_status = ft.Text(
            "CAMERA: INICIALIZANDO", color=MUTED, size=10, weight=ft.FontWeight.BOLD
        )
        self.footer_performance_status = ft.Text(
            "VISAO: AGUARDANDO", color=MUTED, size=10, weight=ft.FontWeight.BOLD
        )
        self.footer_gpio_status = ft.Text(
            "GPIO: SIMULACAO" if config.simulation else "GPIO: REAL",
            color=MUTED,
            size=10,
            weight=ft.FontWeight.BOLD,
        )

        self.nav_buttons: list[ft.Button] = []
        self.content_host = ft.Container(expand=True, padding=18)
        self.views = [self._operation_view(), self._registration_view(), self._settings_view()]

    def build(self) -> None:
        self.page.title = "Separador de Tampas"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed=GREEN, font_family="Roboto")
        self.page.bgcolor = BACKGROUND
        self.page.padding = 0
        self.page.window.width = 1280
        self.page.window.height = 800
        self.page.window.min_width = 1180
        self.page.window.min_height = 700
        self.page.window.resizable = True
        self.page.on_close = self.close

        self.nav_buttons = [
            self._nav_button("OPERACAO", ft.Icons.VIDEOCAM, 0),
            self._nav_button("CADASTRO", ft.Icons.ADD_A_PHOTO, 1),
            self._nav_button("AJUSTES", ft.Icons.SETTINGS, 2),
        ]
        topbar = ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            self.view_context,
                            self.view_title,
                        ],
                        spacing=1,
                    ),
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.DNS_OUTLINED, color=MUTED, size=16),
                                    self.machine_name_display,
                                ],
                                spacing=6,
                            ),
                            ft.Container(
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.SCIENCE_OUTLINED, color="#7A2E0E", size=15),
                                        ft.Text(
                                            "SIMULACAO",
                                            color="#7A2E0E",
                                            weight=ft.FontWeight.BOLD,
                                            size=11,
                                        ),
                                    ],
                                    spacing=6,
                                ),
                                bgcolor=AMBER,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                border_radius=4,
                            ),
                            self.machine_badge_container,
                        ],
                        spacing=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=SURFACE,
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
        )
        sidebar = ft.Container(
            ft.Column(
                [
                    ft.Container(
                        ft.Row(
                            [
                                ft.Container(
                                    ft.Icon(
                                        ft.Icons.PRECISION_MANUFACTURING,
                                        color="#5FE0C1",
                                        size=24,
                                    ),
                                    width=42,
                                    height=42,
                                    alignment=ft.Alignment.CENTER,
                                    bgcolor="#1D2939",
                                    border=ft.Border.all(1, "#344054"),
                                    border_radius=4,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            "SEPARADOR",
                                            color=SURFACE,
                                            weight=ft.FontWeight.BOLD,
                                            size=16,
                                        ),
                                        ft.Text(
                                            "VISION CONTROL",
                                            color="#98A2B3",
                                            size=9,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ],
                                    spacing=0,
                                ),
                            ],
                            spacing=10,
                        ),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=16),
                    ),
                    ft.Divider(color="#344054", height=1),
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text(
                                    "NAVEGACAO",
                                    color="#667085",
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                *self.nav_buttons,
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=16),
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text(
                                    "ESTADO DO SISTEMA",
                                    color="#667085",
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                self._rail_status(
                                    ft.Icons.POWER_SETTINGS_NEW,
                                    "MAQUINA",
                                    self.sidebar_machine_status,
                                ),
                                self._rail_status(
                                    ft.Icons.VIDEOCAM_OUTLINED,
                                    "CAMERA",
                                    self.sidebar_camera_status,
                                ),
                                self._rail_status(
                                    ft.Icons.DATA_OBJECT,
                                    "REFERENCIAS",
                                    self.sidebar_catalog_status,
                                ),
                            ],
                            spacing=13,
                        ),
                        border=ft.Border(top=ft.BorderSide(1, "#344054")),
                        padding=16,
                    ),
                ],
                spacing=0,
                expand=True,
            ),
            width=232,
            bgcolor=HEADER,
        )
        footer = ft.Container(
            ft.Row(
                [
                    self._footer_item(ft.Icons.SECURITY, self.footer_safety_status),
                    self._footer_item(ft.Icons.MEMORY, self.footer_gpio_status),
                    self._footer_item(ft.Icons.CAMERA_ALT_OUTLINED, self.footer_camera_status),
                    self._footer_item(ft.Icons.SPEED, self.footer_performance_status),
                    ft.Container(expand=True),
                    self.footer_output_status,
                ],
                spacing=18,
            ),
            bgcolor=SURFACE,
            border=ft.Border(top=ft.BorderSide(1, BORDER)),
            padding=ft.Padding.symmetric(horizontal=18, vertical=8),
        )
        workspace = ft.Column(
            [topbar, self.content_host, footer],
            spacing=0,
            expand=True,
        )
        self.page.add(ft.Row([sidebar, workspace], spacing=0, expand=True))
        self._show_view(0)
        self._refresh_classes()
        self.page.run_task(self._camera_loop)

    def _nav_button(self, label: str, icon: Any, index: int) -> ft.Button:
        return ft.Button(
            label,
            icon=icon,
            bgcolor="#0E6F61" if index == 0 else HEADER,
            color=SURFACE if index == 0 else "#98A2B3",
            height=46,
            width=208,
            elevation=0,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=4),
                alignment=ft.Alignment.CENTER_LEFT,
                padding=ft.Padding.symmetric(horizontal=14, vertical=0),
            ),
            on_click=lambda _event, selected=index: self._show_view(selected),
        )

    def _show_view(self, index: int) -> None:
        titles = [
            ("PRODUCAO  /  MONITORAMENTO", "Operacao"),
            ("QUALIDADE  /  PADROES VISUAIS", "Cadastro de tampas"),
            ("ENGENHARIA  /  HARDWARE", "Configuracao da maquina"),
        ]
        self.view_context.value, self.view_title.value = titles[index]
        self._current_view_index = index
        self.content_host.content = self.views[index]
        for position, button in enumerate(self.nav_buttons):
            button.bgcolor = "#0E6F61" if position == index else HEADER
            button.color = SURFACE if position == index else "#98A2B3"
        self.page.update()

    def _operation_view(self) -> ft.Row:
        camera_panel = self._panel(
            ft.Column(
                [
                    self._section_header("Inspecao visual", self.camera_badge),
                    ft.Container(
                        self.camera_image,
                        bgcolor="#0C111D",
                        border=ft.Border.all(1, "#344054"),
                        border_radius=4,
                        padding=3,
                        expand=True,
                    ),
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CONVEYOR_BELT, color=MUTED, size=18),
                                    self.conveyor_state,
                                ],
                                spacing=7,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.AIR, color=MUTED, size=18),
                                    self.ejection_state,
                                ],
                                spacing=7,
                            ),
                            ft.Container(expand=True),
                            self.manual_eject_button,
                        ],
                        spacing=16,
                    ),
                ],
                expand=True,
                spacing=10,
            ),
            expand=2,
        )
        result_panel = self._panel(
            ft.Column(
                [
                    self._section_header(
                        "Reconhecimento",
                        ft.Text("TEMPO REAL", color=GREEN, weight=ft.FontWeight.BOLD, size=11),
                    ),
                    ft.Divider(color=BORDER),
                    ft.Text("CLASSE ATUAL", color=MUTED, size=10, weight=ft.FontWeight.BOLD),
                    self.result_name,
                    self.result_detail,
                    self.confidence_bar,
                    ft.Divider(color=BORDER),
                    ft.Text("CONTAGEM POR TIPO", color=MUTED, size=10, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        self.class_counters,
                        bgcolor=SUBTLE,
                        border=ft.Border.all(1, BORDER),
                        padding=10,
                        border_radius=4,
                        expand=True,
                    ),
                    self._metric("TOTAL RECONHECIDO", self.total_count, GREEN_SOFT, GREEN),
                    self.calibrate_button,
                    ft.Row([self.start_button, self.stop_button], spacing=8),
                    self.notice,
                ],
                expand=True,
                spacing=9,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=1,
        )
        return ft.Row([camera_panel, result_panel], spacing=14, expand=True)

    def _registration_view(self) -> ft.Row:
        preview = self._panel(
            ft.Column(
                [
                    self._section_header(
                        "Enquadramento da amostra",
                        ft.Text("CAMERA ATIVA", color=GREEN, weight=ft.FontWeight.BOLD, size=11),
                    ),
                    ft.Container(
                        self.camera_image,
                        bgcolor="#0C111D",
                        border=ft.Border.all(1, "#344054"),
                        border_radius=4,
                        padding=3,
                        expand=True,
                    ),
                    self.class_selector,
                    ft.Row([self.rename_field, self.rename_button], spacing=8),
                    ft.Row(
                        [
                            ft.Button(
                                "CALIBRAR FUNDO",
                                icon=ft.Icons.CENTER_FOCUS_STRONG,
                                bgcolor="#344054",
                                color=SURFACE,
                                height=48,
                                on_click=self._calibrate_background,
                                style=self._button_style(),
                            ),
                            ft.Button(
                                "CAPTURAR AMOSTRA",
                                icon=ft.Icons.CAMERA_ALT,
                                bgcolor=GREEN,
                                color=SURFACE,
                                height=48,
                                expand=True,
                                on_click=self._capture_sample,
                                style=self._button_style(),
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                expand=True,
                spacing=9,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=3,
        )
        form = self._panel(
            ft.Column(
                [
                    self._section_header(
                        "Tipos cadastrados",
                        self.samples_badge,
                    ),
                    self.name_field,
                    ft.Row([self.color_field, self.shape_field], spacing=8),
                    self.output_field,
                    ft.Button(
                        "CADASTRAR TIPO",
                        icon=ft.Icons.ADD,
                        bgcolor=GREEN,
                        color=SURFACE,
                        height=44,
                        on_click=self._create_class,
                        style=self._button_style(),
                    ),
                    ft.Divider(color=BORDER),
                    self.class_list,
                ],
                expand=True,
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=2,
        )
        return ft.Row([preview, form], spacing=14, expand=True)

    def _settings_view(self) -> ft.Container:
        machine_panel = self._panel(
            ft.Column(
                [
                    self._section_header(
                        "Configuracao da maquina",
                        ft.Text("MODO SEGURO", color=GREEN, size=11, weight=ft.FontWeight.BOLD),
                    ),
                    ft.Text("IDENTIFICACAO", color=MUTED, size=9, weight=ft.FontWeight.BOLD),
                    self.machine_name_field,
                    ft.Text("CAPTURA", color=MUTED, size=9, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [self.camera_device_field, self.scan_cameras_button],
                        spacing=6,
                    ),
                    ft.Row(
                        [self.camera_resolution_field, self.camera_fps_field],
                        spacing=8,
                    ),
                    self.conveyor_speed_field,
                    ft.Divider(color=BORDER),
                    ft.Row(
                        [
                            ft.Text(
                                "RECONHECIMENTO",
                                color=MUTED,
                                size=9,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"{self.classifier.reference_count} AMOSTRAS",
                                color=GREEN,
                                size=9,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row([self.min_matches_field, self.min_inliers_field], spacing=8),
                    ft.Row([self.scan_interval_field, self.processing_width_field], spacing=8),
                    ft.Row([self.stable_hits_field, self.background_threshold_field], spacing=8),
                    ft.Row([self.presence_area_field, self.color_weight_field], spacing=8),
                    self.save_machine_button,
                    self.machine_settings_notice,
                ],
                spacing=9,
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=2,
        )
        output_panel = self._panel(
            ft.Column(
                [
                    self._section_header(
                        "Saidas de expulsao",
                        ft.Text("NUMERACAO wPi", color=GREEN, size=11, weight=ft.FontWeight.BOLD),
                    ),
                    self.outputs_list,
                    ft.Divider(color=BORDER),
                    ft.Text("NOVA SAIDA", color=MUTED, size=10, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.new_output_name,
                            self.new_output_gpio,
                            self.new_output_delay,
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            self.new_output_pulse,
                            self.new_output_active_high,
                            ft.Container(expand=True),
                            ft.Button(
                                "ADICIONAR SAIDA",
                                icon=ft.Icons.ADD,
                                bgcolor=GREEN,
                                color=SURFACE,
                                on_click=self._add_output,
                                style=self._button_style(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.settings_notice,
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=3,
        )
        self._refresh_output_settings(update_page=False)
        return ft.Container(
            ft.Row([machine_panel, output_panel], spacing=14, expand=True),
            expand=True,
        )

    def _scan_cameras(self, _event: Any) -> None:
        if not self._settings_edit_allowed():
            return
        self.scan_cameras_button.disabled = True
        self._set_machine_settings_notice("Procurando cameras USB conectadas...")
        self.page.run_task(self._scan_cameras_task)

    async def _scan_cameras_task(self) -> None:
        current_index = self.camera.device

        try:
            reconnected = await asyncio.to_thread(
                self.camera.reconfigure,
                current_index,
                self.config.camera.width,
                self.config.camera.height,
                self.config.camera.fps,
            )
        except Exception as exc:
            self._log.exception("Falha ao reconectar a camera atual")
            self.scan_cameras_button.disabled = False
            self.controller.status.camera_available = False
            self._set_machine_settings_notice(f"Falha ao reconectar a camera: {exc}", error=True)
            return
        if not reconnected:
            self.scan_cameras_button.disabled = False
            self.controller.status.camera_available = False
            self._set_machine_settings_notice(
                "A camera atual foi desconectada e nao forneceu imagem",
                error=True,
            )
            return

        self.controller.status.camera_available = True
        self._current_frame = None
        self.pipeline = ProductionPipeline(
            self.config,
            self.controller,
            self.classifier,
            self._output_for_class,
        )
        self.presence_detector = self.pipeline.presence_detector
        self._reset_stability()
        self.result_name.value = "RECALIBRAR FUNDO"
        self.result_name.color = AMBER
        self.camera_badge.value = "CAMERA ATIVA"
        self.camera_badge.color = GREEN
        self.sidebar_camera_status.value = "CONECTADA"
        self.sidebar_camera_status.color = "#5FE0C1"
        self.footer_camera_status.value = "CAMERA: CONECTADA"
        self.footer_camera_status.color = GREEN

        def detect() -> list[tuple[int, int | None, int | None]]:
            detector = CameraDetector()
            found = [(current_index, self.camera.width, self.camera.height)]
            for index in range(6):
                if index == current_index:
                    continue
                info = detector.probe_device(index)
                if info.available:
                    found.append((info.index, info.width, info.height))
            return sorted(found)

        try:
            cameras = await asyncio.to_thread(detect)
            self.camera_device_field.options = [
                ft.DropdownOption(
                    key=str(index),
                    text=(
                        f"Dispositivo {index} | {width or '?'} x {height or '?'}"
                        + (" (em uso)" if index == current_index else "")
                    ),
                )
                for index, width, height in cameras
            ]
            count = len(cameras)
            self._set_machine_settings_notice(
                f"Camera reconectada; {count} "
                f"{'dispositivo encontrado' if count == 1 else 'dispositivos encontrados'}"
            )
        except Exception as exc:
            self._log.exception("Falha ao procurar cameras")
            self._set_machine_settings_notice(f"Falha ao procurar cameras: {exc}", error=True)
        finally:
            self.scan_cameras_button.disabled = False
            self.page.update()

    def _save_machine_settings(self, _event: Any) -> None:
        if not self._settings_edit_allowed():
            return
        try:
            resolution = (self.camera_resolution_field.value or "").lower().split("x")
            if len(resolution) != 2:
                raise ValueError("Selecione uma resolucao valida")
            values = {
                "name": (self.machine_name_field.value or "").strip(),
                "camera_device": self._parse_non_negative_int(
                    self.camera_device_field.value, "camera"
                ),
                "camera_width": self._parse_positive_int(resolution[0], "largura da camera"),
                "camera_height": self._parse_positive_int(resolution[1], "altura da camera"),
                "camera_fps": self._parse_positive_int(self.camera_fps_field.value, "FPS"),
                "conveyor_speed_mm_s": self._parse_positive(
                    self.conveyor_speed_field.value, "velocidade da esteira"
                ),
                "min_good_matches": self._parse_positive_int(
                    self.min_matches_field.value, "correspondencias minimas"
                ),
                "min_inliers": self._parse_positive_int(
                    self.min_inliers_field.value, "pontos geometricos"
                ),
                "scan_interval_ms": self._parse_positive_int(
                    self.scan_interval_field.value, "intervalo de analise"
                ),
                "stable_hits": self._parse_positive_int(
                    self.stable_hits_field.value, "confirmacoes"
                ),
                "background_threshold": self._parse_positive_int(
                    self.background_threshold_field.value, "sensibilidade do fundo"
                ),
                "min_foreground_ratio": self._parse_percentage(
                    self.presence_area_field.value,
                    "area minima",
                ),
                "max_image_width": self._parse_positive_int(
                    self.processing_width_field.value, "largura de processamento"
                ),
                "color_weight": self._parse_percentage(
                    self.color_weight_field.value,
                    "peso da cor",
                ),
            }
            if not values["name"]:
                raise ValueError("Informe o nome da maquina")
        except ValueError as exc:
            self._set_machine_settings_notice(str(exc), error=True)
            return

        self.save_machine_button.disabled = True
        self._set_machine_settings_notice("Aplicando configuracao...")
        self.page.run_task(self._apply_machine_settings, values)

    async def _apply_machine_settings(self, values: dict[str, Any]) -> None:
        previous = self.config
        previous_camera = (
            previous.camera.device,
            previous.camera.width,
            previous.camera.height,
            previous.camera.fps,
        )
        requested_camera = (
            values["camera_device"],
            values["camera_width"],
            values["camera_height"],
            values["camera_fps"],
        )
        camera_changed = requested_camera != previous_camera

        try:
            if camera_changed:
                opened = await asyncio.to_thread(self.camera.reconfigure, *requested_camera)
                if not opened:
                    raise SettingsError("A camera selecionada nao forneceu imagem")
                values["camera_width"] = self.camera.width
                values["camera_height"] = self.camera.height

            try:
                updated = await asyncio.to_thread(
                    self.settings_store.save_machine_settings,
                    **values,
                )
            except Exception:
                if camera_changed:
                    await asyncio.to_thread(self.camera.reconfigure, *previous_camera)
                raise

            self.controller.reconfigure_machine(updated)
            recognition_changed = updated.recognition != previous.recognition
            presence_changed = camera_changed or (
                updated.recognition.background_threshold
                != previous.recognition.background_threshold
                or updated.recognition.min_foreground_ratio
                != previous.recognition.min_foreground_ratio
            )
            self.config = updated
            self.classifier.ratio_threshold = updated.recognition.ratio_threshold
            self.classifier.min_good_matches = updated.recognition.min_good_matches
            self.classifier.min_inliers = updated.recognition.min_inliers
            self.classifier.ambiguity_ratio = updated.recognition.ambiguity_ratio
            self.classifier.max_image_width = updated.recognition.max_image_width
            self.classifier.color_weight = updated.recognition.color_weight
            if presence_changed:
                self.result_name.value = "RECALIBRAR FUNDO"
                self.result_name.color = AMBER

            previous_presence = None if presence_changed else self.presence_detector
            self.pipeline = ProductionPipeline(
                updated,
                self.controller,
                self.classifier,
                self._output_for_class,
                presence_detector=previous_presence,
            )
            self.presence_detector = self.pipeline.presence_detector
            self._reset_stability()

            self.machine_name_display.value = updated.name.upper()
            self.page.title = f"{updated.name} | Separador de Tampas"
            self.camera_device_field.options = [
                ft.DropdownOption(
                    key=str(updated.camera.device),
                    text=f"Dispositivo {updated.camera.device} (em uso)",
                )
            ]
            self.camera_device_field.value = str(updated.camera.device)
            actual_resolution = f"{updated.camera.width}x{updated.camera.height}"
            available_resolutions = [
                option.key for option in self.camera_resolution_field.options
            ]
            if actual_resolution not in available_resolutions:
                self.camera_resolution_field.options.append(
                    ft.DropdownOption(
                        key=actual_resolution,
                        text=actual_resolution.replace("x", " x "),
                    )
                )
            self.camera_resolution_field.value = actual_resolution
            self.sidebar_camera_status.value = "CONECTADA"
            self.sidebar_camera_status.color = "#5FE0C1"
            self.footer_camera_status.value = f"CAMERA {updated.camera.device}: CONECTADA"
            self.footer_camera_status.color = GREEN
            message = "Configuracao salva"
            if presence_changed:
                message += "; calibre novamente o fundo"
            elif recognition_changed:
                message += "; reconhecimento atualizado"
            self._set_machine_settings_notice(message)
        except (SettingsError, ValueError, OSError, RuntimeError) as exc:
            self._set_machine_settings_notice(str(exc), error=True)
        finally:
            self.save_machine_button.disabled = False
            self.page.update()

    def _set_machine_settings_notice(self, message: str, error: bool = False) -> None:
        self.machine_settings_notice.value = message
        self.machine_settings_notice.color = RED if error else GREEN
        self.page.update()

    def _refresh_output_settings(self, update_page: bool = True) -> None:
        self.outputs_list.controls = []
        for name, output in self.config.outputs.items():
            gpio_field = ft.TextField(
                label="GPIO wPi",
                value="" if output.gpio is None else str(output.gpio),
                dense=True,
                keyboard_type=ft.KeyboardType.NUMBER,
                width=125,
            )
            delay_field = ft.TextField(
                label="Atraso (ms)",
                value=self._format_number(self._output_delay_ms(output)),
                dense=True,
                keyboard_type=ft.KeyboardType.NUMBER,
                width=140,
            )
            pulse_field = ft.TextField(
                label="Pulso (ms)",
                value=self._format_number(output.pulse_ms),
                dense=True,
                keyboard_type=ft.KeyboardType.NUMBER,
                width=130,
            )
            active_high = ft.Switch(label="Nivel alto", value=output.active_high)
            pin_detail = self._pin_detail(output.gpio)
            self.outputs_list.controls.append(
                ft.Container(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                name.replace("_", " ").upper(),
                                                color=INK,
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(pin_detail, color=MUTED, size=10),
                                        ],
                                        spacing=1,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.SAVE,
                                        icon_color=GREEN,
                                        tooltip="Salvar saida",
                                        on_click=lambda _event,
                                        output_name=name,
                                        gpio=gpio_field,
                                        delay=delay_field,
                                        pulse=pulse_field,
                                        level=active_high: self._save_output(
                                            output_name,
                                            gpio,
                                            delay,
                                            pulse,
                                            level,
                                        ),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=RED,
                                        tooltip="Excluir saida",
                                        on_click=lambda _event, output_name=name: self._delete_output(
                                            output_name
                                        ),
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                [
                                    gpio_field,
                                    delay_field,
                                    pulse_field,
                                    active_high,
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=7,
                    ),
                    bgcolor=SUBTLE,
                    border=ft.Border.all(1, BORDER),
                    border_radius=4,
                    padding=10,
                )
            )
        if update_page:
            self.page.update()

    def _save_output(
        self,
        name: str,
        gpio_field: ft.TextField,
        delay_field: ft.TextField,
        pulse_field: ft.TextField,
        active_high: ft.Switch,
    ) -> None:
        if not self._settings_edit_allowed():
            return
        try:
            updated = self.settings_store.save_output(
                name=name,
                gpio=self._parse_gpio(gpio_field.value),
                delay_ms=self._parse_non_negative(delay_field.value, "atraso"),
                pulse_ms=self._parse_positive(pulse_field.value, "pulso"),
                active_high=bool(active_high.value),
            )
            self._apply_output_config(updated)
            self._set_settings_notice(f"Saida {name} atualizada")
        except (SettingsError, ValueError, OSError) as exc:
            self._set_settings_notice(str(exc), error=True)

    def _add_output(self, _event: Any) -> None:
        if not self._settings_edit_allowed():
            return
        try:
            updated = self.settings_store.save_output(
                name=self.new_output_name.value,
                gpio=self._parse_gpio(self.new_output_gpio.value),
                delay_ms=self._parse_non_negative(self.new_output_delay.value, "atraso"),
                pulse_ms=self._parse_positive(self.new_output_pulse.value, "pulso"),
                active_high=bool(self.new_output_active_high.value),
                create=True,
            )
            created_name = self.new_output_name.value.strip().lower().replace(" ", "_")
            self.new_output_name.value = ""
            self.new_output_gpio.value = ""
            self._apply_output_config(updated)
            self._set_settings_notice(f"Saida {created_name} adicionada")
        except (SettingsError, ValueError, OSError) as exc:
            self._set_settings_notice(str(exc), error=True)

    def _delete_output(self, name: str) -> None:
        if not self._settings_edit_allowed():
            return
        used_by = [
            item["name"]
            for item in self.catalog.list_classes()
            if item.get("output") == name
        ]
        if used_by:
            self._set_settings_notice(
                f"Saida em uso por: {', '.join(used_by)}",
                error=True,
            )
            return
        try:
            updated = self.settings_store.delete_output(name)
            self._apply_output_config(updated)
            self._set_settings_notice(f"Saida {name} excluida")
        except (SettingsError, ValueError, OSError) as exc:
            self._set_settings_notice(str(exc), error=True)

    def _apply_output_config(self, updated: MachineConfig) -> None:
        self.controller.reconfigure_outputs(updated.outputs)
        self.config = updated
        self.footer_output_status.value = f"SAIDAS: {len(updated.outputs)}"
        self.output_field.options = [
            ft.DropdownOption(key=name, text=name.replace("_", " ").upper())
            for name in updated.outputs
        ]
        if self.output_field.value not in updated.outputs:
            self.output_field.value = next(iter(updated.outputs))
        self._refresh_output_settings(update_page=False)
        self.page.update()

    def _settings_edit_allowed(self) -> bool:
        if self.controller.status.running:
            message = "Pare a maquina antes de alterar a configuracao"
            self._set_settings_notice(message, error=True)
            self._set_machine_settings_notice(message, error=True)
            return False
        return True

    def _set_settings_notice(self, message: str, error: bool = False) -> None:
        self.settings_notice.value = message
        self.settings_notice.color = RED if error else GREEN
        self.page.update()

    def _output_delay_ms(self, output: OutputConfig) -> float:
        if output.delay_ms is not None:
            return output.delay_ms
        travel_ms = output.distance_mm / self.config.conveyor.speed_mm_s * 1000
        compensation_ms = (
            self.config.timing.processing_latency_ms + self.config.timing.valve_response_ms
        )
        return max(0.0, travel_ms - compensation_ms)

    @staticmethod
    def _pin_detail(gpio: int | None) -> str:
        known = {
            19: "wPi 19 | pino fisico 29 | PD0",
            20: "wPi 20 | pino fisico 31 | PD1",
        }
        if gpio is None:
            return "GPIO nao atribuido"
        return known.get(gpio, f"wPi {gpio}")

    @staticmethod
    def _parse_gpio(value: str | None) -> int | None:
        text = (value or "").strip()
        if not text:
            return None
        gpio = int(text)
        if gpio < 0:
            raise ValueError("GPIO nao pode ser negativo")
        return gpio

    @staticmethod
    def _parse_non_negative(value: str | None, label: str) -> float:
        number = float((value or "").strip().replace(",", "."))
        if number < 0:
            raise ValueError(f"{label.capitalize()} nao pode ser negativo")
        return number

    @staticmethod
    def _parse_positive(value: str | None, label: str) -> float:
        number = float((value or "").strip().replace(",", "."))
        if number <= 0:
            raise ValueError(f"{label.capitalize()} deve ser maior que zero")
        return number

    @staticmethod
    def _parse_positive_int(value: str | None, label: str) -> int:
        number = float((value or "").strip().replace(",", "."))
        if number <= 0 or not number.is_integer():
            raise ValueError(f"{label.capitalize()} deve ser um numero inteiro maior que zero")
        return int(number)

    @staticmethod
    def _parse_non_negative_int(value: str | None, label: str) -> int:
        number = float((value or "").strip().replace(",", "."))
        if number < 0 or not number.is_integer():
            raise ValueError(f"{label.capitalize()} deve ser um numero inteiro valido")
        return int(number)

    @staticmethod
    def _parse_percentage(value: str | None, label: str) -> float:
        percentage = float((value or "").strip().replace(",", "."))
        if not 0 < percentage < 100:
            raise ValueError(f"{label.capitalize()} deve estar entre 0 e 100%")
        return percentage / 100

    @staticmethod
    def _format_number(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    @staticmethod
    def _rail_status(icon: Any, label: str, value: ft.Text) -> ft.Row:
        return ft.Row(
            [
                ft.Icon(icon, color="#5FE0C1", size=18),
                ft.Column(
                    [
                        ft.Text(label, color="#667085", size=8, weight=ft.FontWeight.BOLD),
                        value,
                    ],
                    spacing=0,
                    expand=True,
                ),
            ],
            spacing=9,
        )

    @staticmethod
    def _footer_item(icon: Any, value: str | ft.Text) -> ft.Row:
        text_control = (
            value
            if isinstance(value, ft.Text)
            else ft.Text(value, color=MUTED, size=10, weight=ft.FontWeight.BOLD)
        )
        return ft.Row([ft.Icon(icon, color=GREEN, size=15), text_control], spacing=5)

    @staticmethod
    def _button_style() -> ft.ButtonStyle:
        return ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))

    @staticmethod
    def _panel(content: ft.Control, expand: int | bool) -> ft.Container:
        return ft.Container(
            content,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            padding=16,
            border_radius=6,
            expand=expand,
        )

    @staticmethod
    def _section_header(title: str, trailing: ft.Control) -> ft.Row:
        return ft.Row(
            [ft.Text(title, color=INK, size=15, weight=ft.FontWeight.BOLD), trailing],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    @staticmethod
    def _metric(label: str, value: ft.Text, background: str, accent: str) -> ft.Container:
        return ft.Container(
            ft.Column(
                [ft.Text(label, color=MUTED, size=10, weight=ft.FontWeight.BOLD), value],
                spacing=0,
            ),
            bgcolor=background,
            padding=12,
            border=ft.Border(
                top=ft.BorderSide(1, BORDER),
                right=ft.BorderSide(1, BORDER),
                bottom=ft.BorderSide(1, BORDER),
                left=ft.BorderSide(4, accent),
            ),
            border_radius=4,
            expand=True,
        )

    def _start(self, _event: Any) -> None:
        if not self.camera.opened:
            self._set_notice("A camera nao esta disponivel", error=True)
            return
        if self.classifier.reference_count == 0:
            self._set_notice("Cadastre ao menos uma imagem antes de iniciar", error=True)
            return
        if not self.presence_detector.calibrated:
            self._set_notice("Retire o objeto e pressione CALIBRAR FUNDO", error=True)
            return
        self.controller.start()
        self.pipeline.reset()
        self.machine_badge.value = "EM OPERACAO"
        self.machine_status_icon.color = "#5FE0C1"
        self.machine_badge_container.bgcolor = "#075E54"
        self.machine_badge_container.border = ft.Border.all(1, "#0E8A78")
        self.sidebar_machine_status.value = "EM OPERACAO"
        self.sidebar_machine_status.color = "#5FE0C1"
        self.footer_safety_status.value = "PRODUCAO ATIVA"
        self.footer_safety_status.color = GREEN
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self._set_notice("Reconhecimento iniciado")

    def _stop(self, _event: Any) -> None:
        self.controller.stop()
        self.machine_badge.value = "PARADO"
        self.machine_status_icon.color = "#98A2B3"
        self.machine_badge_container.bgcolor = "#344054"
        self.machine_badge_container.border = ft.Border.all(1, "#475467")
        self.sidebar_machine_status.value = "PARADA SEGURA"
        self.sidebar_machine_status.color = "#D0D5DD"
        self.footer_safety_status.value = "ESTADO SEGURO"
        self.footer_safety_status.color = MUTED
        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.result_name.value = "PARADO"
        self.result_detail.value = "0% DE CONFIANCA"
        self.confidence_bar.value = 0
        self._reset_stability()
        self._set_notice("Maquina parada em seguranca")

    def _manual_eject(self, _event: Any) -> None:
        if not self.controller.status.running:
            self._set_notice("Inicie a maquina antes de testar o jato", error=True)
            return
        output_name = next(iter(self.config.outputs))
        self.controller.schedule_ejection(output_name, immediate=True)
        self._set_notice(f"Pulso manual agendado em {output_name}")

    def _calibrate_background(self, _event: Any) -> None:
        if self._current_frame is None:
            self._set_notice("A camera ainda nao forneceu uma imagem", error=True)
            return
        if self.controller.status.running:
            self._stop(_event)
        try:
            self.pipeline.calibrate(self._current_frame)
        except RoiError as exc:
            self._set_notice(
                f"{exc}; selecione a resolucao real da camera em Ajustes",
                error=True,
            )
            return
        self.result_name.value = "FUNDO CALIBRADO"
        self.result_name.color = GREEN
        self.result_detail.value = "PRONTO PARA INICIAR"
        self.confidence_bar.value = 0
        self._last_result = ClassificationResult(None, "AGUARDANDO", 0.0, 0, 0, False)
        self._reset_stability()
        self._set_notice("Fundo vazio registrado")

    def _create_class(self, _event: Any) -> None:
        try:
            created = self.catalog.create_class(
                self.name_field.value,
                self.color_field.value or "outra",
                self.shape_field.value or "outro",
                self.output_field.value or next(iter(self.config.outputs)),
            )
        except CatalogError as exc:
            self._set_notice(str(exc), error=True)
            return
        self.name_field.value = ""
        self._selected_class_id = created["id"]
        self._refresh_classes()
        self._set_notice("Tipo cadastrado; capture pelo menos tres amostras")

    def _select_class(self, event: Any) -> None:
        self._selected_class_id = event.control.value
        self._sync_rename_field()
        self.page.update()

    def _rename_class(self, _event: Any) -> None:
        if not self._selected_class_id:
            self._set_notice("Selecione uma classe para renomear", error=True)
            return
        classes = self.catalog.list_classes()
        current = next(
            (item for item in classes if item["id"] == self._selected_class_id),
            None,
        )
        if current is None:
            self._set_notice("Classe de tampa nao encontrada", error=True)
            return
        try:
            renamed = self.catalog.rename_class(self._selected_class_id, self.rename_field.value)
            self.controller.rename_class_counter(current["name"], renamed["name"])
            self.classifier.reload()
            if self._last_result.class_id == self._selected_class_id:
                self._last_result = ClassificationResult(
                    self._last_result.class_id,
                    renamed["name"],
                    self._last_result.confidence,
                    self._last_result.good_matches,
                    self._last_result.inliers,
                    self._last_result.accepted,
                    self._last_result.color_similarity,
                )
                self.result_name.value = renamed["name"].upper()
            self._refresh_classes()
            self._set_notice("Classe renomeada para " + renamed["name"])
        except CatalogError as exc:
            self._set_notice(str(exc), error=True)

    def _capture_sample(self, _event: Any) -> None:
        if not self._selected_class_id:
            self._set_notice("Selecione uma classe para a captura", error=True)
            return
        if self._current_frame is None:
            self._set_notice("A camera ainda nao forneceu uma imagem", error=True)
            return
        import cv2

        detection = None
        presence_mask = None
        if self.presence_detector.calibrated:
            try:
                presence = self.presence_detector.analyze(self._current_frame)
                presence_mask = presence.mask
                detections = self.pipeline.detector.detect(
                    self._current_frame,
                    self.config.camera.roi,
                    presence.mask,
                )
                registration_box = self._registration_box(self._current_frame)
                candidates = [
                    item
                    for item in detections
                    if self._point_in_box(
                        item.centroid_x,
                        item.centroid_y,
                        registration_box,
                    )
                ]
                detection = max(candidates, key=lambda item: item.area, default=None)
            except (ValueError, RoiError):
                detection = None

        if detection is None:
            x, y, width, height = self._registration_box(self._current_frame)
            sample_frame = self._current_frame[y : y + height, x : x + width]
        else:
            sample_frame, _sample_mask = self.pipeline.crop_detection(
                self._current_frame,
                detection.bounding_box,
                presence_mask,
            )
        ok, encoded = cv2.imencode(".jpg", sample_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            self._set_notice("Falha ao preparar a imagem", error=True)
            return
        try:
            self.catalog.add_sample(self._selected_class_id, encoded.tobytes(), "image/jpeg")
            self.classifier.reload()
            self._refresh_classes()
            self._set_notice("Amostra cadastrada e classificador atualizado")
        except CatalogError as exc:
            self._set_notice(str(exc), error=True)

    def _refresh_classes(self) -> None:
        classes = self.catalog.list_classes()
        sample_count = sum(len(item.get("samples", [])) for item in classes)
        self.samples_badge.value = f"{sample_count} {'AMOSTRA' if sample_count == 1 else 'AMOSTRAS'}"
        self.sidebar_catalog_status.value = self.samples_badge.value
        if self._selected_class_id is None and classes:
            self._selected_class_id = classes[0]["id"]
        self.class_selector.options = [
            ft.DropdownOption(key=item["id"], text=item["name"]) for item in classes
        ]
        self.class_selector.value = self._selected_class_id
        self._sync_rename_field(classes)
        self.class_list.controls = []
        for cap_class in classes:
            self.class_list.controls.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LABEL, color=GREEN, size=20),
                            ft.Column(
                                [
                                    ft.Text(cap_class["name"], weight=ft.FontWeight.BOLD, size=12),
                                    ft.Text(
                                        f"{len(cap_class['samples'])} imagens | {cap_class['output']}",
                                        color=MUTED,
                                        size=10,
                                    ),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                        ]
                    ),
                    bgcolor=SUBTLE,
                    border=ft.Border.all(1, BORDER),
                    padding=10,
                    border_radius=4,
                )
            )
            for sample in reversed(cap_class.get("samples", [])):
                image_path = self.catalog.media_path(cap_class["id"], sample["filename"])
                thumbnail: ft.Control
                if image_path is not None:
                    thumbnail = ft.Image(
                        src=image_path.read_bytes(),
                        width=70,
                        height=44,
                        fit=ft.BoxFit.COVER,
                        border_radius=3,
                        gapless_playback=True,
                    )
                else:
                    thumbnail = ft.Icon(ft.Icons.BROKEN_IMAGE, color=MUTED, size=28)
                self.class_list.controls.append(
                    ft.Container(
                        ft.Row(
                            [
                                thumbnail,
                                ft.Column(
                                    [
                                        ft.Text("IMAGEM CADASTRADA", size=10, weight=ft.FontWeight.BOLD),
                                        ft.Text(sample["filename"], color=MUTED, size=9),
                                    ],
                                    spacing=1,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=RED,
                                    tooltip="Excluir imagem",
                                    on_click=lambda _event, class_id=cap_class["id"], filename=sample[
                                        "filename"
                                    ]: self._delete_sample(class_id, filename),
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                    )
                )
        self._refresh_counts()
        self.page.update()

    def _sync_rename_field(self, classes: list[dict[str, Any]] | None = None) -> None:
        available = classes if classes is not None else self.catalog.list_classes()
        selected = next(
            (item for item in available if item["id"] == self._selected_class_id),
            None,
        )
        self.rename_field.disabled = selected is None
        self.rename_button.disabled = selected is None
        self.rename_field.value = selected["name"] if selected is not None else ""

    def _delete_sample(self, class_id: str, filename: str) -> None:
        try:
            self.catalog.delete_sample(class_id, filename)
            self.classifier.reload()
            self._refresh_classes()
            self._set_notice("Imagem excluida e classificador atualizado")
        except CatalogError as exc:
            self._set_notice(str(exc), error=True)

    async def _camera_loop(self) -> None:
        opened = self.camera.opened
        self.controller.status.camera_available = opened
        if not opened:
            self.camera_badge.value = "CAMERA INDISPONIVEL"
            self.camera_badge.color = RED
            self.sidebar_camera_status.value = "INDISPONIVEL"
            self.sidebar_camera_status.color = "#FDA29B"
            self.footer_camera_status.value = "CAMERA: FALHA"
            self.footer_camera_status.color = RED
            self._set_notice("Feche outros aplicativos que estejam usando a camera", error=True)
            return

        self.camera_badge.value = "CAMERA ATIVA"
        self.camera_badge.color = GREEN
        self.sidebar_camera_status.value = "CONECTADA"
        self.sidebar_camera_status.color = "#5FE0C1"
        self.footer_camera_status.value = "CAMERA: CONECTADA"
        self.footer_camera_status.color = GREEN
        self.page.update()
        consecutive_read_failures = 0
        while self._active:
            try:
                self.controller.tick()
            except Exception:
                self._show_safe_ui("Falha no controle de saidas; maquina parada")
                await asyncio.sleep(0.1)
                continue
            try:
                ok, frame = await asyncio.to_thread(self.camera.read)
            except Exception:
                self._log.exception("Falha ao ler a camera")
                ok, frame = False, None
            if not ok or frame is None:
                consecutive_read_failures += 1
                if (
                    self.controller.status.running
                    and consecutive_read_failures >= self.config.camera.max_read_failures
                ):
                    self.controller.report_camera_failure("falha consecutiva na camera")
                    self._show_safe_ui("Falha na camera; maquina parada")
                await asyncio.sleep(0.1)
                continue
            consecutive_read_failures = 0
            self.controller.status.camera_available = True
            self.camera_badge.value = "CAMERA ATIVA"
            self.camera_badge.color = GREEN
            self.sidebar_camera_status.value = "CONECTADA"
            self.sidebar_camera_status.color = "#5FE0C1"
            self.footer_camera_status.value = "CAMERA: CONECTADA"
            self.footer_camera_status.color = GREEN
            self._current_frame = frame.copy()
            now = time.monotonic()
            self.pipeline.record_capture(now)
            interval = self.config.recognition.scan_interval_ms / 1000
            if self.controller.status.running and now - self._last_scan >= interval:
                self._last_scan = now
                try:
                    pipeline_result = await asyncio.to_thread(
                        self.pipeline.process,
                        frame,
                        now,
                    )
                    self._active_tracks = pipeline_result.tracks
                    self._last_latency_ms = self.pipeline.metrics.classification_ms
                    self.footer_performance_status.value = (
                        f"CAP {self.pipeline.metrics.capture_fps:.1f} FPS | "
                        f"PROC {self.pipeline.metrics.processing_fps:.1f} FPS | "
                        f"{self.pipeline.metrics.average_latency_ms:.0f} MS"
                    )
                    self.footer_performance_status.color = GREEN
                    self._handle_pipeline_result(pipeline_result)
                except Exception:
                    self._log.exception("Falha no reconhecimento")
                    self.controller.enter_safe_state("falha no reconhecimento")
                    self._show_safe_ui("Falha no reconhecimento; maquina parada")

            if now - self._last_display >= 0.1:
                self._last_display = now
                display_frame = self._annotate_frame(
                    frame,
                    self._last_result,
                    self._active_tracks,
                )
                self.camera_image.src = self._encode_frame(display_frame)
                self.page.update()
            await asyncio.sleep(0.02)

    def _handle_pipeline_result(self, pipeline_result: PipelineResult) -> None:
        result = pipeline_result.last_classification
        self._last_result = result
        if not pipeline_result.detections:
            self._handle_no_object(pipeline_result.presence.foreground_ratio)
            self._refresh_counts()
            return
        self.result_name.value = result.class_name
        self.result_detail.value = (
            f"{round(result.confidence * 100)}% DE CONFIANCA | "
            f"COR {round(result.color_similarity * 100)}% | "
            f"{result.inliers} PONTOS | {round(self._last_latency_ms)} MS"
        )
        self.confidence_bar.value = result.confidence
        if result.accepted:
            self.result_name.color = GREEN
        else:
            self.result_name.color = RED
        self._refresh_counts()

    def _handle_no_object(self, foreground_ratio: float) -> None:
        self.result_name.value = "SEM OBJETO"
        self.result_name.color = MUTED
        self.result_detail.value = f"FUNDO ESTAVEL | ALTERACAO {foreground_ratio * 100:.1f}%"
        self.confidence_bar.value = 0

    def _refresh_counts(self) -> None:
        self.total_count.value = str(self.controller.status.total_caps)
        classes = self.catalog.list_classes()
        self.class_counters.controls = []
        for cap_class in classes:
            count = self.controller.status.counters_by_class.get(cap_class["name"], 0)
            self.class_counters.controls.append(
                ft.Row(
                    [
                        ft.Text(
                            cap_class["name"],
                            color=INK,
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Container(
                            ft.Text(str(count), color=SURFACE, weight=ft.FontWeight.BOLD, size=13),
                            bgcolor=GREEN,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=4,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
        if not classes:
            self.class_counters.controls.append(ft.Text("Nenhuma classe cadastrada", color=MUTED))
        self.conveyor_state.value = (
            "ESTEIRA LIGADA" if self.controller.status.conveyor_running else "ESTEIRA PARADA"
        )
        self.conveyor_state.color = GREEN if self.controller.status.conveyor_running else MUTED
        count = self.controller.status.scheduled_ejections
        self.ejection_state.value = f"{count} {'JATO' if count == 1 else 'JATOS'}"

    def _reset_stability(self) -> None:
        self.pipeline.reset()
        self._active_tracks = []

    def _output_for_class(self, class_id: str) -> str | None:
        cap_class = next(
            (item for item in self.catalog.list_classes() if item["id"] == class_id),
            None,
        )
        return None if cap_class is None else str(cap_class["output"])

    def _show_safe_ui(self, message: str) -> None:
        self.machine_badge.value = "FALHA"
        self.machine_status_icon.color = "#FDA29B"
        self.machine_badge_container.bgcolor = RED
        self.sidebar_machine_status.value = "PARADA POR FALHA"
        self.sidebar_machine_status.color = "#FDA29B"
        self.footer_safety_status.value = "ESTADO SEGURO"
        self.footer_safety_status.color = RED
        self.start_button.disabled = False
        self.stop_button.disabled = True
        self._reset_stability()
        self._set_notice(message, error=True)

    def _set_notice(self, message: str, error: bool = False) -> None:
        self.notice.value = message
        self.notice.color = RED if error else MUTED
        self.page.update()

    def _annotate_frame(
        self,
        frame: Any,
        result: ClassificationResult,
        tracks: list[TrackedCap] | None = None,
    ) -> Any:
        import cv2

        rendered = frame.copy()
        try:
            roi = resolve_roi(rendered, self.config.camera.roi)
        except RoiError:
            height, width = rendered.shape[:2]
            cv2.rectangle(rendered, (2, 2), (width - 3, height - 3), (0, 0, 220), 3)
            cv2.putText(
                rendered,
                "ROI INVALIDA - AJUSTE A RESOLUCAO DA CAMERA",
                (20, 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 220),
                2,
                cv2.LINE_AA,
            )
            return rendered
        x1, y1, x2, y2 = roi.x, roi.y, roi.x2, roi.y2
        color = (91, 127, 8) if result.accepted else (91, 196, 49)
        cv2.rectangle(rendered, (x1, y1), (x2, y2), color, 3)
        if self._current_view_index == 1:
            guide_x, guide_y, guide_width, guide_height = self._registration_box(rendered)
            cv2.rectangle(
                rendered,
                (guide_x, guide_y),
                (guide_x + guide_width, guide_y + guide_height),
                (0, 196, 255),
                3,
            )
        for cap in tracks or []:
            x, y, width, height = cap.bounding_box
            track_color = (30, 180, 70) if cap.class_id else (0, 170, 255)
            cv2.rectangle(rendered, (x, y), (x + width, y + height), track_color, 2)
            label = f"ID {cap.id}"
            if cap.class_id:
                label += f" | {cap.class_name}"
            cv2.putText(
                rendered,
                label,
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                track_color,
                2,
                cv2.LINE_AA,
            )
        if result.class_name not in {"AGUARDANDO", "NAO RECONHECIDO"}:
            cv2.rectangle(rendered, (x1, y1 - 42), (min(x2, x1 + 520), y1), color, -1)
            cv2.putText(
                rendered,
                f"{result.class_name}  {round(result.confidence * 100)}%",
                (x1 + 10, y1 - 13),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        return rendered

    def _registration_box(self, frame: Any) -> tuple[int, int, int, int]:
        roi = resolve_roi(frame, self.config.camera.roi)
        width = max(1, int(roi.width * 0.60))
        height = max(1, int(roi.height * 0.70))
        x = roi.x + (roi.width - width) // 2
        y = roi.y + (roi.height - height) // 2
        return x, y, width, height

    @staticmethod
    def _point_in_box(
        x: float,
        y: float,
        box: tuple[int, int, int, int],
    ) -> bool:
        box_x, box_y, width, height = box
        return box_x <= x <= box_x + width and box_y <= y <= box_y + height

    @staticmethod
    def _encode_frame(frame: Any) -> bytes:
        import cv2

        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        return encoded.tobytes() if ok else b""

    @staticmethod
    def _placeholder_image() -> bytes:
        import cv2
        import numpy as np

        frame = np.full((720, 1280, 3), (32, 37, 42), dtype=np.uint8)
        cv2.putText(
            frame,
            "ABRINDO CAMERA",
            (445, 375),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            (157, 165, 173),
            2,
            cv2.LINE_AA,
        )
        return FletMachineApp._encode_frame(frame)

    def close(self, _event: Any = None) -> None:
        self._active = False
        self.camera.close()
        self.controller.stop()


def run_flet_interface(
    controller: MachineController,
    config: MachineConfig,
    config_path: str | Path = "config/machine.yaml",
) -> None:
    camera = CameraStream(
        config.camera.device,
        config.camera.width,
        config.camera.height,
        config.camera.fps,
    )
    camera.open()

    async def main(page: ft.Page) -> None:
        app = FletMachineApp(page, controller, config, camera, config_path)
        app.build()

    ft.run(main, name="Separador de Tampas", view=ft.AppView.FLET_APP)
