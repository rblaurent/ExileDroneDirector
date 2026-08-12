"""Fresh-process recovery and independence proof for published private clone."""

from __future__ import annotations

import unreal

PREFIX = "EDD_PUBLISHED_CLONE_RESTART"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Server/Repository/BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
SOURCE_ID, CLONE_ID = "clone-source-a", "clone-target-b"
OWNER_A, OWNER_B = "clone-owner-a", "clone-owner-b"
DOC = {
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "RegionId": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "DurationSeconds": ("DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"),
    "ContentHash": ("ContentHash", "content_hash", "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"),
}
def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(value, message):
    if not value: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def names(value):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in value).lstrip("_")
    return value, unreal.Name(value), snake, unreal.Name(snake)
def prop(obj, name):
    for candidate in names(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read {name}")
def set_prop(obj, name, value):
    for candidate in names(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"could not set {name}")
def doc_prop(document, name):
    for candidate in DOC[name]:
        try: return document.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read document {name}")
def set_doc(document, name, value):
    for candidate in DOC[name]:
        try: document.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"could not set document {name}")
def cleanup():
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"delete failed {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"cleanup failed {slot}")
def decode(actor, flypath_id):
    i=list(prop(actor,"ActiveFlypathIdsV1")).index(flypath_id)
    set_prop(actor,"ScratchEncodedRecordV1",list(prop(actor,"ActiveRecordEnvelopesV1"))[i])
    actor.call_method("DecodeRecordV1"); require(bool(prop(actor,"ScratchValidV1")),f"decode failed {flypath_id}")
def stage_clone_save(actor):
    # Begin with the owner-loaded clone so every schema field and Blueprint UDS
    # array keeps its native identity; then modify only the intended edit.
    document=prop(actor,"ResultDraftDocumentV1")
    set_doc(document,"RevisionNumber",999); set_doc(document,"RegionId","ExiledLands")
    set_doc(document,"DurationSeconds",44.0); set_doc(document,"ContentHash","ignored")
    set_prop(actor,"ScratchDocumentV1",document); actor.call_method("EncodeDocumentV1"); actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor,"ScratchValidV1")),"restart document fixture failed")
    set_prop(actor,"RequestDraftDocumentV1",prop(actor,"ScratchDocumentV1"))

actor=None
try:
    cls=unreal.load_class(None,CLASS_PATH); subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor=subsystem.spawn_actor_from_class(cls,unreal.Vector(0,0,-100000),unreal.Rotator(),False)
    require(actor is not None,"spawn failed"); actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor,"RepositoryLoadedV1")),"recovery failed")
    require((int(prop(actor,"ActiveGenerationV1")),str(prop(actor,"ActiveSlotV1")))==(7,"EDD_Repository_A"),"recovered generation/slot changed")
    require(list(prop(actor,"ActiveFlypathIdsV1"))==[SOURCE_ID,CLONE_ID],"recovered ID order changed")
    emit("RECOVERY","PASS")

    set_prop(actor,"RequestRequesterAccountIdV1",OWNER_A); set_prop(actor,"RequestFlypathIdV1",CLONE_ID)
    actor.call_method("LoadDraftV1"); require(prop(actor,"ResultCodeV1")=="Forbidden","wrong owner loaded recovered clone")
    set_prop(actor,"RequestRequesterAccountIdV1",OWNER_B); actor.call_method("LoadDraftV1")
    require(prop(actor,"ResultCodeV1")=="Success","owner could not load recovered clone")
    require(int(doc_prop(prop(actor,"ResultDraftDocumentV1"),"RevisionNumber"))==1,"recovered clone revision changed")
    require(abs(float(doc_prop(prop(actor,"ResultDraftDocumentV1"),"DurationSeconds"))-22.0)<0.001,"recovered clone content changed")
    decode(actor,CLONE_ID)
    require(prop(actor,"ScratchRecordVisibilityV1")=="private","recovered clone leaked public")
    require(prop(actor,"ScratchRecordOwnerAccountIdV1")==OWNER_B,"recovered clone owner changed")
    require(bool(prop(actor,"ScratchRecordHasSourceAttributionV1")),"recovered attribution missing")
    require(prop(actor,"ScratchRecordSourceFlypathIdV1")==SOURCE_ID,"recovered source ID changed")
    require(int(prop(actor,"ScratchRecordSourceRevisionNumberV1"))==2,"recovered source revision changed")
    require(prop(actor,"ScratchRecordSourceTitleV1")=="Published Original","recovered source title changed")
    require(prop(actor,"ScratchRecordSourceCreatorDisplayNameV1")=="Source Author A","recovered creator changed")
    emit("PRIVATE_OWNER_BOUNDARY","PASS"); emit("ATTRIBUTION","PASS")

    # Edit clone after restart. Source draft/published snapshot must remain independent.
    set_prop(actor,"RequestFlypathIdV1",CLONE_ID); set_prop(actor,"RequestExpectedRevisionV1",1)
    set_prop(actor,"RequestNowUtcV1","2026-08-12T04:08:00Z"); stage_clone_save(actor)
    actor.call_method("SaveDraftV1"); require(prop(actor,"ResultCodeV1")=="Success","recovered clone save failed")
    require((int(prop(actor,"ActiveGenerationV1")),str(prop(actor,"ActiveSlotV1")))==(8,"EDD_Repository_B"),"clone save generation changed")
    require(int(prop(actor,"ResultCurrentRevisionV1"))==2,"clone revision did not advance")
    decode(actor,CLONE_ID)
    require(abs(float(doc_prop(prop(actor,"ScratchRecordDraftDocumentV1"),"DurationSeconds"))-44.0)<0.001,"clone save content changed")
    require(int(prop(actor,"ScratchRecordSourceRevisionNumberV1"))==2,"clone save mutated attribution")
    decode(actor,SOURCE_ID)
    require(int(prop(actor,"ScratchRecordDraftRevisionNumberV1"))==4,"clone save mutated source draft revision")
    require(abs(float(doc_prop(prop(actor,"ScratchRecordDraftDocumentV1"),"DurationSeconds"))-123.0)<0.001,"clone save mutated source draft")
    require(int(prop(actor,"ScratchRecordPublishedRevisionNumberV1"))==2,"clone save mutated source published revision")
    require(abs(float(doc_prop(prop(actor,"ScratchRecordPublishedDocumentV1"),"DurationSeconds"))-22.0)<0.001,"clone save mutated source published snapshot")
    emit("BIDIRECTIONAL_INDEPENDENCE","PASS")

    latest=unreal.GameplayStatics.load_game_from_slot("EDD_Repository_B",0)
    require(latest is not None and int(prop(latest,"Generation"))==8 and bool(prop(latest,"Committed")),"restart commit changed")
    emit("SAVEGAME_RESTART_WRITE","PASS"); emit("RESULT","PASS")
finally:
    if actor is not None: unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
    cleanup(); emit("CLEANUP","PASS")
