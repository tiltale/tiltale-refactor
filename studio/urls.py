"""TilTale routes."""

from django.urls import path

from . import views

app_name: str = "studio"

urlpatterns = [
    path("", views.home, name="home"),
    path("new/", views.new_project, name="new_project"),
    path("guide/", views.quick_guide, name="quick_guide"),
    path("develop/", views.develop, name="develop"),
    path("develop/regenerate/", views.regenerate, name="regenerate"),
    path("develop/config/", views.project_config, name="config"),
    path("develop/flowchart/", views.flowchart, name="flowchart"),
    path("develop/frames/new/", views.new_frame, name="new_frame"),
    path("develop/edit/<slug:frame_name>/", views.frame_editor, name="frame_editor"),
    path("develop/edit/<slug:frame_name>/delete/", views.delete_frame, name="delete_frame"),
    path("develop/edit/<slug:frame_name>/elements/add/", views.add_element, name="add_element"),
    path("develop/elements/<int:element_id>/save/", views.save_element, name="save_element"),
    path("develop/elements/<int:element_id>/delete/", views.delete_element, name="delete_element"),
    path("results/", views.results, name="results"),
    path("results/import/", views.import_logs, name="import_logs"),
    path("results/session/<str:file_name>/", views.session_detail, name="session_detail"),
    path("api/status/", views.status_api, name="status_api"),
    path("api/elements/<int:element_id>/position/", views.element_position_api, name="element_position_api"),
    path("api/frames/<slug:frame_name>/flow-position/", views.flow_position_api, name="flow_position_api"),
    path("api/study-log/", views.study_log_api, name="study_log_api"),
    path("preview/<path:path>", views.preview_file, name="preview_file"),
    path("materials/<path:path>", views.material_file, name="material_file"),
]
