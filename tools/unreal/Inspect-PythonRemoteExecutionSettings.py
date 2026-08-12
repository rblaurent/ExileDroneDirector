"""Report the exact Enhanced DevKit Python remote-execution config owner.

This is a diagnostic commandlet seam, not an editor mutation.  It prevents
repeated preference-window exploration when provisioning a fresh DevKit.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PYTHON_REMOTE_SETTINGS"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


for class_name in ("PythonScriptPluginSettings", "PythonScriptPluginUserSettings"):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        cls = unreal.load_class(
            None, f"/Script/PythonScriptPlugin.{class_name}"
        )
    if cls is None:
        emit("CLASS_MISSING", class_name)
        continue
    obj = unreal.get_default_object(cls)
    emit("CLASS", f"{class_name}|{obj.get_class().get_path_name()}")
    emit(
        "CLASS_ATTRIBUTES",
        f"{class_name}|{','.join(name for name in dir(cls) if 'config' in name.lower() or 'property' in name.lower())}",
    )
    emit(
        "ATTRIBUTES",
        f"{class_name}|{','.join(name for name in dir(obj) if 'remote' in name.lower() or 'python' in name.lower())}",
    )
    for property_name in (
        "remote_execution",
        "remote_execution_multicast_group_endpoint",
        "remote_execution_multicast_bind_address",
        "remote_execution_send_buffer_size_bytes",
        "remote_execution_receive_buffer_size_bytes",
        "remote_execution_multicast_ttl",
    ):
        try:
            emit("PROPERTY", f"{class_name}|{property_name}|{obj.get_editor_property(property_name)}")
        except Exception as error:
            emit("PROPERTY_MISSING", f"{class_name}|{property_name}|{error}")

    try:
        for native_property_name in (
            "bRemoteExecution",
            "RemoteExecutionMulticastGroupEndpoint",
            "RemoteExecutionMulticastBindAddress",
            "RemoteExecutionSendBufferSizeBytes",
            "RemoteExecutionReceiveBufferSizeBytes",
            "RemoteExecutionMulticastTtl",
        ):
            unreal.SystemLibrary.execute_console_command(
                None,
                f"getall {class_name} {native_property_name}",
            )
            emit("GETALL", f"{class_name}|{native_property_name}|REQUESTED")
    except Exception as error:
        emit("GETALL_FAILED", f"{class_name}|{error}")

emit("RESULT", "PASS")
