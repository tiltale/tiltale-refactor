"""Every TilTale route. Open the matching function in views.py to change a page."""

from django.urls import path

from . import views

app_name: str = "studio"

urlpatterns = [
    path("", views.home, name="home"),
    path("new/", views.new_project, name="new_project"),
    path("help/", views.help_page, name="help"),

    path("develop/", views.develop, name="develop"),
    path("develop/regenerate/", views.regenerate, name="regenerate"),
    path("develop/playtest/", views.playtest, name="playtest"),
    path("develop/config/", views.project_config, name="config"),
    path("develop/flowchart/", views.flowchart, name="flowchart"),
    path("develop/flowchart/tidy/", views.tidy_flowchart, name="tidy_flowchart"),
    path("develop/frames/new/", views.new_frame, name="new_frame"),
    path("develop/frames/<int:frame_id>/", views.frame_editor, name="frame_editor"),
    path("develop/frames/<int:frame_id>/delete/", views.delete_frame, name="delete_frame"),
    path("develop/frames/<int:frame_id>/elements/add/", views.add_element, name="add_element"),
    path("develop/frames/<int:frame_id>/images/add/", views.add_image, name="add_image"),
    path("develop/frames/<int:frame_id>/elements/import/", views.import_elements, name="import_elements"),
    path("develop/elements/<int:element_id>/save/", views.save_element, name="save_element"),
    path("develop/elements/<int:element_id>/duplicate/", views.duplicate_element, name="duplicate_element"),
    path("develop/elements/<int:element_id>/move/", views.move_element, name="move_element"),
    path("develop/elements/<int:element_id>/content/add/", views.add_content_for_element, name="add_content_for_element"),
    path("develop/elements/<int:element_id>/delete/", views.delete_element, name="delete_element"),

    path("results/", views.results, name="results"),
    path("results/import/", views.import_logs, name="import_logs"),
    path("results/session/<str:file_name>/", views.session_detail, name="session_detail"),

    path("api/elements/<int:element_id>/position/", views.element_position_api, name="element_position_api"),
    path("api/frames/<int:frame_id>/background/", views.background_box_api, name="background_box_api"),
    path("api/flow-positions/", views.flow_positions_api, name="flow_positions_api"),
    path("api/logs/<str:file_name>/", views.log_api, name="log_api"),

    # Must stay above "preview/<path>": the preview's log.php is answered by Django.
    path("preview/log.php", views.preview_log, name="preview_log"),
    path("preview/<path:path>", views.preview_file, name="preview_file"),
    path("materials/<path:path>", views.material_file, name="material_file"),
    path("branding/<str:name>", views.branding, name="branding"),
]
