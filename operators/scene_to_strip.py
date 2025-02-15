# Using code and timings from Gabriel Montagné's https://github.com/gabrielmontagne/blender-addon-unfurl-fountain

import bpy

from .. import fountain
from pathlib import Path

from collections import namedtuple
from math import ceil
from pathlib import Path
import bpy
import os
import re
import sys
from bpy.props import IntProperty, StringProperty
from bpy.types import SequenceEditor, Scene

spaces = re.compile(r'\s+')
words_per_second = 3.75
text_speed_factor = 1.2
min_text_length = 1.5
line_break_seconds = 0.3
scene_padding_seconds = 1

Scene = namedtuple('Scene', ['name', 'elements'])
Dialogue = namedtuple('Dialogue', ['seconds', 'character', 'parenthetical', 'text'])
Action = namedtuple('Action', ['seconds', 'text'])

def text_to_seconds(text):
    words = len(spaces.split(text))
    return max(min_text_length, round(words / words_per_second + line_break_seconds * text.count('\n'), 2))

def find_empty_channel():
    context = bpy.context

    scene = context.scene
    screenwriter_channel = scene.screenwriter_channel

    if not context.scene.sequence_editor:
        context.scene.sequence_editor_create()

    sequences = context.scene.sequence_editor.sequences

    if screenwriter_channel > 0:
        if sequences:
            ss = [s for s in sequences if s.channel >= screenwriter_channel and s.channel <= screenwriter_channel + 2]
            for s in ss:
                sequences.remove(s)

        return screenwriter_channel

    if not sequences:
        return 1

    channels = [s.channel for s in sequences]
    channels = sorted(list(set(channels)))
    return channels[-1] + 1

def find_completely_empty_channel():
    if not bpy.context.scene.sequence_editor:
        bpy.context.scene.sequence_editor_create()   
    sequences = bpy.context.sequences
    if not sequences:
        addSceneChannel = 1
    else:
        channels = [s.channel for s in sequences]
        channels = sorted(list(set(channels)))
        empty_channel = channels[-1] + 1
        addSceneChannel = empty_channel
    return addSceneChannel

def seconds_to_frames(seconds):
    render = bpy.context.scene.render
    return ceil((render.fps / render.fps_base) * seconds)

def to_scenes(script):
    F = fountain.Fountain(script)
    scenes = []

    current_scene = None
    current_char = None
    current_parenthetical = ''

    for fc, f in enumerate(F.elements):
        element_type = f.element_type
        text = f.element_text.strip()

        if element_type == 'Scene Heading':
            name = f.original_content.strip()
            current_scene = Scene(name, [])
            scenes.append(current_scene)

        elif not current_scene:
            continue

        elif element_type == 'Parenthetical':
            current_parenthetical = text

        elif element_type == 'Character':
            current_char = text

        elif element_type == 'Dialogue':
            seconds = text_to_seconds(text) * text_speed_factor
            current_scene.elements.append(
                Dialogue(
                seconds,
                current_char,
                current_parenthetical,
                text
            ))
            current_parenthetical = ''

        elif current_scene and element_type == 'Action':
            seconds = text_to_seconds(text)
            current_scene.elements.append(Action(seconds, text))

    return scenes


def lay_out_scenes(scenes):
    next = 0
    channel = find_empty_channel()+10
    font_size = int(bpy.context.scene.render.resolution_y/18)

    for i, s in enumerate(scenes):
        total = scene_padding_seconds

        for e in s.elements:
            start = total
            end = total + e.seconds

            element_type = type(e)
            if element_type is Dialogue:
                strip = create_strip(
                    channel + 1,
                    start + next,
                    end + next,
                    ('{}{}\n{}').format((e.character).upper(), (
                        e.parenthetical and '\n' + e.parenthetical),
                        e.text)
                )

                strip.location.y = 0.1
                strip.align_y = 'BOTTOM'
                strip.location.x = 0.05
                strip.align_x = 'LEFT'
                strip.font_size = font_size          

            elif element_type is Action:
                strip = create_strip(channel + 2, start + next, end + next, e.text)
                strip.location.x = 0.05
                strip.location.y = 0.92
                strip.align_y = 'TOP'
                strip.align_x = 'LEFT'
                strip.font_size = font_size

            else:
                strip = create_strip(channel + 2, start + next, end + next, e.text)
                strip.location.x = 0.05
                strip.location.y = 0.92
                strip.align_y = 'TOP'
                strip.align_x = 'LEFT'
                strip.font_size = font_size

            total = end

        total += scene_padding_seconds
        end = next + total

        strip = create_strip(channel, next, next + total, (s.name).upper())
        strip.location.x = 0.05
        strip.location.y = 1.0
        strip.align_y = 'TOP'
        strip.align_x = 'LEFT'
        strip.font_size = font_size

        create_scenes_objects(1, next, next + total, i)

        next = end

def create_strip(channel, start, end, text):
    frame_start = seconds_to_frames(start)
    frame_end = seconds_to_frames(end)

    strip = bpy.context.scene.sequence_editor.sequences.new_effect(
        name=text,
        type='TEXT',
        channel=channel,
        frame_start=frame_start,
        frame_end=frame_end
    )

    strip.font_size = int(bpy.context.scene.render.resolution_y/18)
    strip.use_shadow = True
    strip.select= True
    strip.wrap_width = 0.85
    strip.text = text
    strip.blend_type = 'ALPHA_OVER'
    return strip


def create_scenes_objects(channel, start, end, text):
    frame_start = seconds_to_frames(start)
    frame_end = seconds_to_frames(end)

    fountain_script = bpy.context.area.spaces.active.text.as_string()
    if fountain_script.strip() == "": return {"CANCELLED"}

    F = fountain.Fountain(fountain_script)

    # add scene strips
    f_collected = []
    s_collected = []
    found_scene = ""

    # Find scene names.
    for s in bpy.data.scenes:
        s_collected.append(s.name)

    # Find scene headings.        
    for fc, f in enumerate(F.elements):
        if f.element_type == 'Scene Heading':
            f_collected.append(f)

    # Create scenes.
    render = bpy.context.scene.render
    fps = round((render.fps / render.fps_base), 3)
    for fc, f in enumerate(f_collected):
        if text == fc:
            if bpy.context.scene.screenwriter_numbers == True:
                # if scene is major of 99
                if len(f_collected)>99:
                    number = "{:0>3d}".format(fc + 1)
                else:
                    number = "{:0>2d}".format(fc + 1)
                # Add number
                name = number + " " + str(f.element_text.title())
            else:
                name = str(f.element_text.title())

            if name in s_collected:
                new_scene = bpy.data.scenes[name]
            else:
                # Set context to base scene and duplicate
                if bpy.context.scene.screenwriter_base_scene is None:
                    new_scene = bpy.data.scenes.new(name=name)
                else:
                    scene_prv = bpy.context.scene
                    bpy.context.window.scene = bpy.context.scene.screenwriter_base_scene
                    bpy.ops.scene.new(type='FULL_COPY')
                    bpy.context.window.scene.name = name
                    new_scene = bpy.data.scenes[name]
                    bpy.context.window.scene = scene_prv
                    scene_prv.update_tag()

                # falta borrar la secuencia de video
                #for i in (bpy.context.scene.sequence_editor.sequences_all):
                #    bpy.context.scene.sequence_editor.sequences.remove(i)
                #bpy.context.scene.sequence_editor.sequences.remove(bpy.context.scene.sequence_editor.active_strip)

                #print(bpy.context.scene.sequence_editor.sequences_all[i].frame_start)
                #print(bpy.context.scene.sequence_editor.sequences_all[i].frame_final_duration)

            new_scene.master_sequence = bpy.context.scene.name
            bpy.context.scene.master_sequence = bpy.context.scene.name
            if bpy.context.scene.screenwriter_general_timeline == True:
                new_scene.render.fps_base = render.fps_base
                new_scene.render.fps = render.fps
                new_scene.render.resolution_x = render.resolution_x
                new_scene.render.resolution_y = render.resolution_y
                new_scene.frame_start = frame_start
                new_scene.frame_end = frame_end
            else:
                new_scene.frame_end = frame_end - frame_start

            n = 0
            for shot_count, shot in enumerate(F.elements):
                if shot.element_type == 'Scene Heading':
                    #if str(shot.element_text.title()) == str(f.element_text.title()):
                    if text == n:
                        found_scene = str(shot.element_text.title())
                        shot_camera = 0
                    else:
                        found_scene = ""
                # Add shots as cameras.
                if found_scene and (shot.element_type == 'Comment' or shot.element_type == 'Action'):
                    regex = "\\[\\[SHOT:(?i)(.*?)\\]\\]"
                    matches = re.findall(regex, shot.element_text)
                    for match in matches:
                        bpy.ops.object.camera_add(rotation=(1.5708, 0, 0))
                        bpy.context.object.data.type = 'ORTHO'
                        bpy.context.object.data.ortho_scale = 3.2
                        bpy.context.object.name = match
                        new_object = bpy.data.objects[bpy.context.object.name]
                        bpy.ops.transform.translate(value=(shot_camera * 4, 0, 0))
                        bpy.data.scenes[new_scene.name].collection.objects.link(new_object)
                        bpy.ops.object.delete(use_global=False, confirm=False)
                        shot_camera += 1
                        # Add scene strips.
                        sse = bpy.context.scene.sequence_editor
                        newScene=sse.sequences.new_scene(match, new_scene, channel+shot_camera, frame_start)
                        sse.sequences_all[newScene.name].scene_camera = new_object
                        sse.sequences_all[newScene.name].animation_offset_start = 0
                        sse.sequences_all[newScene.name].frame_final_end = frame_end
                        sse.sequences_all[newScene.name].frame_start = frame_start

    # Add objects.
    for fc, f in enumerate(f_collected):
        if text == fc:
        #if text == f.original_content.strip():
            key =""
            heading = ""

            for kc, k in enumerate(F.elements):
                if k.element_type == 'Scene Heading':
                    heading = k.element_text.title()
                if (
                    heading == f.element_text.title()
                    and k.element_type in ("Character", "Dialogue", "Action", "Scene Heading")
                ):                   
                    key += (str(k.element_text)+' ')

            # Are there any keywords?           
            props = bpy.context.scene.keywords_assigner
            camera = 0
            if props.keywords and key:                
                for p in range(len(props.keywords)):
                    keyword = props.keywords[p]           
                    if key.lower().find((keyword.name).lower()) > -1:
                        # Go through all objects of current keyword.                    
                        for obj in keyword.objects:
                            # Check if object exists.
                            if obj.objectname in bpy.data.objects: #  and obj not in bpy.data.scenes[new_scene.name].collection.objects[:]
                                try:
                                    # Link object to scene.
                                    new_object = bpy.data.objects[obj.objectname]
                                    bpy.data.scenes[new_scene.name].collection.objects.link(new_object)
                                except:
                                    pass
                                # Add scene strip.                                
                                if (obj.objecttype).lower() == "camera":
                                    sse = bpy.context.scene.sequence_editor
                                    newScene=sse.sequences.new_scene(obj.objectname, new_scene, channel+camera, frame_start)
                                    sse.sequences_all[newScene.name].scene_camera = bpy.data.objects[obj.objectname]
                                    sse.sequences_all[newScene.name].animation_offset_start = 0
                                    sse.sequences_all[newScene.name].frame_final_end = frame_end
                                    sse.sequences_all[newScene.name].frame_start = frame_start
                                    camera +=1
            # Add MultiCam strip if several cameras added.
            if camera > 1:
                sse = bpy.context.scene.sequence_editor
                newMulticam = sse.sequences.new_effect(
                    name="Multicam",
                    type='MULTICAM',
                    channel=channel+camera,
                    frame_start=frame_start,
                    frame_end=frame_end
                    )
                sse.sequences_all[newMulticam.name].multicam_source=channel 
            # Add Scene Strip if no camera-object added.
            elif camera == 0:
                newScene=bpy.context.scene.sequence_editor.sequences.new_scene(f.element_text.title(), new_scene, channel, frame_start)
                #bpy.context.scene.sequence_editor.sequences_all[newScene.name].scene_camera = bpy.data.objects[cam.name]
                #bpy.context.scene.sequence_editor.sequences_all[newScene.name].animation_offset_start = 0
                bpy.context.scene.sequence_editor.sequences_all[newScene.name].frame_final_end = frame_end
                bpy.context.scene.sequence_editor.sequences_all[newScene.name].frame_start = frame_start
            break
    bpy.ops.sequencer.set_range_to_strips()

    return {'FINISHED'}


class SCREENWRITER_OT_strips_to_markers(bpy.types.Operator):
    '''Add Strip Markers'''
    bl_idname = "screenwriter.strips_to_markers"
    bl_label = "Insert a Marker for each Strip"

    def execute(self, context):
        selected_frames = {s.frame_start for s in context.selected_sequences}
        timeline_markers = context.scene.timeline_markers
        for frame in selected_frames:
            timeline_markers.new(name='F_{}'.format(frame), frame=frame)

        return {'FINISHED'}
    
class SCREENWRITER_OT_clear_markers(bpy.types.Operator):
    '''Remove All Markers'''
    bl_idname = "screenwriter.clear_markers"
    bl_label = "Clear All Markers"

    def execute(self, context):
        context.scene.timeline_markers.clear()
        return { 'FINISHED' }


class SCREENWRITER_OT_to_strips(bpy.types.Operator):
    '''Convert foutain to text strips'''
    bl_idname = "screenwriter.fountain_to_strips"
    bl_label = "Generate Scenes & Strips"

    @classmethod
    def poll(cls, context):
        space = bpy.context.space_data
        try:
            filepath = space.text.name
            if filepath.strip() == "": return False
            return ((space.type == 'TEXT_EDITOR')
                    and Path(filepath).suffix == ".fountain")
        except AttributeError: return False

    def execute(self, context):

        script = bpy.context.area.spaces.active.text.as_string()
        if script.strip() == "": return {"CANCELLED"}

        scenes = to_scenes(script)
        lay_out_scenes(scenes)

        return {"FINISHED"}


class SCREENWRITER_OT_specific_to_strips(bpy.types.Operator):
    '''Convert specific foutain to text strips'''
    bl_idname = "screenwriter.fountain_specific_to_strips"
    bl_label = "Convert specific foutain to strips"

    text: StringProperty(name='File to process')

    def execute(self, context):

        if not self.text: return {"CANCELLED"}

        file = bpy.data.texts.get(self.text)

        if not file:
            return {"CANCELLED"}


        script = file.as_string()
        if script.strip() == "": return {"CANCELLED"}

        scenes = to_scenes(script)
        lay_out_scenes(scenes)

        return {"FINISHED"}
