#!/usr/bin/env python
# -*- coding: utf-8 -*-

#This file is part of PLCOpenEditor, a library implementing an IEC 61131-3 editor
#based on the plcopen standard. 
#
#Copyright (C) 2012: Edouard TISSERANT and Laurent BESSARD
#
#See COPYING file for copyrights details.
#
#This library is free software; you can redistribute it and/or
#modify it under the terms of the GNU General Public
#License as published by the Free Software Foundation; either
#version 2.1 of the License, or (at your option) any later version.
#
#This library is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#General Public License for more details.
#
#You should have received a copy of the GNU General Public
#License along with this library; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from types import TupleType
from time import time as gettime
import math
import numpy

import wx
import wx.lib.buttons

import matplotlib
matplotlib.use('WX')
import matplotlib.pyplot
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import _convert_agg_to_wx_bitmap
from matplotlib.backends.backend_agg import FigureCanvasAgg
from mpl_toolkits.mplot3d import Axes3D
color_cycle = ['r', 'b', 'g', 'm', 'y', 'k']
cursor_color = '#800080'

from editors.DebugViewer import DebugViewer, REFRESH_PERIOD
from controls.DebugVariablePanel.DebugVariableItem import DebugVariableItem
from dialogs.ForceVariableDialog import ForceVariableDialog
from util.BitmapLibrary import GetBitmap

class DebugVariableDropTarget(wx.TextDropTarget):
    
    def __init__(self, parent, control=None):
        wx.TextDropTarget.__init__(self)
        self.ParentWindow = parent
        self.ParentControl = control
    
    def __del__(self):
        self.ParentWindow = None
        self.ParentControl = None
    
    def OnDragOver(self, x, y, d):
        if self.ParentControl is not None:
            self.ParentControl.OnMouseDragging(x, y)
        else:
            self.ParentWindow.RefreshHighlight(x, y)
        return wx.TextDropTarget.OnDragOver(self, x, y, d)
        
    def OnDropText(self, x, y, data):
        message = None
        try:
            values = eval(data)
        except:
            message = _("Invalid value \"%s\" for debug variable")%data
            values = None
        if not isinstance(values, TupleType):
            message = _("Invalid value \"%s\" for debug variable")%data
            values = None
        
        if message is not None:
            wx.CallAfter(self.ShowMessage, message)
        elif values is not None and values[1] == "debug":
            if self.ParentControl is not None:
                width, height = self.ParentControl.GetSize()
                target_idx = self.ParentControl.GetIndex()
                merge_type = GRAPH_PARALLEL
                if isinstance(self.ParentControl, DebugVariableGraphic):
                    if self.ParentControl.Is3DCanvas():
                        if y > height / 2:
                            target_idx += 1
                        if len(values) > 1 and values[2] == "move":
                            self.ParentWindow.MoveValue(values[0], target_idx)
                        else:
                            self.ParentWindow.InsertValue(values[0], target_idx, force=True)
                        
                    else:
                        rect = self.ParentControl.GetAxesBoundingBox()
                        if rect.InsideXY(x, y):
                            merge_rect = wx.Rect(rect.x, rect.y, rect.width / 2., rect.height)
                            if merge_rect.InsideXY(x, y):
                                merge_type = GRAPH_ORTHOGONAL
                            wx.CallAfter(self.ParentWindow.MergeGraphs, values[0], target_idx, merge_type, force=True)
                        else:
                            if y > height / 2:
                                target_idx += 1
                            if len(values) > 2 and values[2] == "move":
                                self.ParentWindow.MoveValue(values[0], target_idx)
                            else:
                                self.ParentWindow.InsertValue(values[0], target_idx, force=True)
                else:
                    if y > height / 2:
                        target_idx += 1
                    if len(values) > 2 and values[2] == "move":
                        self.ParentWindow.MoveValue(values[0], target_idx)
                    else:
                        self.ParentWindow.InsertValue(values[0], target_idx, force=True)
                    
            elif len(values) > 2 and values[2] == "move":
                self.ParentWindow.MoveValue(values[0])
            else:
                self.ParentWindow.InsertValue(values[0], force=True)
    
    def OnLeave(self):
        self.ParentWindow.ResetHighlight()
        return wx.TextDropTarget.OnLeave(self)
    
    def ShowMessage(self, message):
        dialog = wx.MessageDialog(self.ParentWindow, message, _("Error"), wx.OK|wx.ICON_ERROR)
        dialog.ShowModal()
        dialog.Destroy()

MILLISECOND = 1000000
SECOND = 1000 * MILLISECOND
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR

ZOOM_VALUES = map(lambda x:("x %.1f" % x, x), [math.sqrt(2) ** i for i in xrange(8)])
RANGE_VALUES = \
    [("%dms" % i, i * MILLISECOND) for i in (10, 20, 50, 100, 200, 500)] + \
    [("%ds" % i, i * SECOND) for i in (1, 2, 5, 10, 20, 30)] + \
    [("%dm" % i, i * MINUTE) for i in (1, 2, 5, 10, 20, 30)] + \
    [("%dh" % i, i * HOUR) for i in (1, 2, 3, 6, 12, 24)]

GRAPH_PARALLEL, GRAPH_ORTHOGONAL = range(2)

SCROLLBAR_UNIT = 10

#CANVAS_HIGHLIGHT_TYPES
[HIGHLIGHT_NONE,
 HIGHLIGHT_BEFORE,
 HIGHLIGHT_AFTER,
 HIGHLIGHT_LEFT,
 HIGHLIGHT_RIGHT,
 HIGHLIGHT_RESIZE] = range(6)

HIGHLIGHT_DROP_PEN = wx.Pen(wx.Colour(0, 128, 255))
HIGHLIGHT_DROP_BRUSH = wx.Brush(wx.Colour(0, 128, 255, 128))
HIGHLIGHT_RESIZE_PEN = wx.Pen(wx.Colour(200, 200, 200))
HIGHLIGHT_RESIZE_BRUSH = wx.Brush(wx.Colour(200, 200, 200))

#CANVAS_SIZE_TYPES
[SIZE_MINI, SIZE_MIDDLE, SIZE_MAXI] = [0, 100, 200]

DEFAULT_CANVAS_HEIGHT = 200.
CANVAS_BORDER = (20., 10.)
CANVAS_PADDING = 8.5
VALUE_LABEL_HEIGHT = 17.
AXES_LABEL_HEIGHT = 12.75

def compute_mask(x, y):
    mask = []
    for xp, yp in zip(x, y):
        if xp == yp:
            mask.append(xp)
        else:
            mask.append("*")
    return mask

def NextTick(variables):
    next_tick = None
    for item, data in variables:
        if len(data) > 0:
            if next_tick is None:
                next_tick = data[0][0]
            else:
                next_tick = min(next_tick, data[0][0])
    return next_tick

def OrthogonalData(item, start_tick, end_tick):
    data = item.GetData(start_tick, end_tick)
    min_value, max_value = item.GetValueRange()
    if min_value is not None and max_value is not None:
        center = (min_value + max_value) / 2.
        range = max(1.0, max_value - min_value)
    else:
        center = 0.5
        range = 1.0
    return data, center - range * 0.55, center + range * 0.55

class GraphButton():
    
    def __init__(self, x, y, bitmap, callback):
        self.Position = wx.Point(x, y)
        self.Bitmap = bitmap
        self.Shown = True
        self.Enabled = True
        self.Callback = callback
    
    def __del__(self):
        self.callback = None
    
    def GetSize(self):
        return self.Bitmap.GetSize()
    
    def SetPosition(self, x, y):
        self.Position = wx.Point(x, y)
    
    def Show(self):
        self.Shown = True
        
    def Hide(self):
        self.Shown = False
    
    def IsShown(self):
        return self.Shown
    
    def Enable(self):
        self.Enabled = True
    
    def Disable(self):
        self.Enabled = False
    
    def IsEnabled(self):
        return self.Enabled
    
    def HitTest(self, x, y):
        if self.Shown and self.Enabled:
            w, h = self.Bitmap.GetSize()
            rect = wx.Rect(self.Position.x, self.Position.y, w, h)
            if rect.InsideXY(x, y):
                return True
        return False
    
    def ProcessCallback(self):
        if self.Callback is not None:
            wx.CallAfter(self.Callback)
            
    def Draw(self, dc):
        if self.Shown and self.Enabled:
            dc.DrawBitmap(self.Bitmap, self.Position.x, self.Position.y, True)

class DebugVariableViewer:
    
    def __init__(self, window, items=[]):
        self.ParentWindow = window
        self.Items = items
        
        self.Highlight = HIGHLIGHT_NONE
        self.Buttons = []
    
    def __del__(self):
        self.ParentWindow = None
    
    def GetIndex(self):
        return self.ParentWindow.GetViewerIndex(self)
    
    def GetItem(self, variable):
        for item in self.Items:
            if item.GetVariable() == variable:
                return item
        return None
    
    def GetItems(self):
        return self.Items
    
    def GetVariables(self):
        if len(self.Items) > 1:
            variables = [item.GetVariable() for item in self.Items]
            if self.GraphType == GRAPH_ORTHOGONAL:
                return tuple(variables)
            return variables
        return self.Items[0].GetVariable()
    
    def AddItem(self, item):
        self.Items.append(item)
        
    def RemoveItem(self, item):
        if item in self.Items:
            self.Items.remove(item)
        
    def Clear(self):
        for item in self.Items:
            self.ParentWindow.RemoveDataConsumer(item)
        self.Items = []
        
    def IsEmpty(self):
        return len(self.Items) == 0
    
    def UnregisterObsoleteData(self):
        for item in self.Items[:]:
            iec_path = item.GetVariable()
            if self.ParentWindow.GetDataType(iec_path) is None:
                self.ParentWindow.RemoveDataConsumer(item)
                self.RemoveItem(item)
            else:
                self.ParentWindow.AddDataConsumer(iec_path.upper(), item)
                item.RefreshVariableType()
        
    def ResetData(self):
        for item in self.Items:
            item.ResetData()
    
    def RefreshViewer(self):
        pass
    
    def SetHighlight(self, highlight):
        if self.Highlight != highlight:
            self.Highlight = highlight
            return True
        return False
    
    def GetButtons(self):
        return self.Buttons
    
    def HandleButtons(self, x, y):
        for button in self.GetButtons():
            if button.HitTest(x, y):
                button.ProcessCallback()
                return True
        return False
    
    def IsOverButton(self, x, y):
        for button in self.GetButtons():
            if button.HitTest(x, y):
                return True
        return False
    
    def ShowButtons(self, show):
        for button in self.Buttons:
            if show:
                button.Show()
            else:
                button.Hide()
        self.RefreshButtonsState()
        self.ParentWindow.ForceRefresh()
    
    def RefreshButtonsState(self, refresh_positions=False):
        if self:
            width, height = self.GetSize()
            if refresh_positions:
                offset = 0
                buttons = self.Buttons[:]
                buttons.reverse()
                for button in buttons:
                    w, h = button.GetSize()
                    button.SetPosition(width - 5 - w - offset, 5)
                    offset += w + 2
                self.ParentWindow.ForceRefresh()
    
    def DrawCommonElements(self, dc, buttons=None):
        width, height = self.GetSize()
        
        dc.SetPen(HIGHLIGHT_DROP_PEN)
        dc.SetBrush(HIGHLIGHT_DROP_BRUSH)
        if self.Highlight in [HIGHLIGHT_BEFORE]:
            dc.DrawLine(0, 1, width - 1, 1)
        elif self.Highlight in [HIGHLIGHT_AFTER]:
            dc.DrawLine(0, height - 1, width - 1, height - 1)
        
        if buttons is None:
            buttons = self.Buttons
        for button in buttons:
            button.Draw(dc)
            
        if self.ParentWindow.IsDragging():
            destBBox = self.ParentWindow.GetDraggingAxesClippingRegion(self)
            srcPos = self.ParentWindow.GetDraggingAxesPosition(self)
            if destBBox.width > 0 and destBBox.height > 0:
                srcPanel = self.ParentWindow.DraggingAxesPanel
                srcBBox = srcPanel.GetAxesBoundingBox()
                
                if destBBox.x == 0:
                    srcX = srcBBox.x - srcPos.x
                else:
                    srcX = srcBBox.x
                if destBBox.y == 0:
                    srcY = srcBBox.y - srcPos.y
                else:
                    srcY = srcBBox.y
                
                srcBmp = _convert_agg_to_wx_bitmap(srcPanel.get_renderer(), None)
                srcDC = wx.MemoryDC()
                srcDC.SelectObject(srcBmp)
                
                dc.Blit(destBBox.x, destBBox.y, 
                        int(destBBox.width), int(destBBox.height), 
                        srcDC, srcX, srcY)
    
    def OnEnter(self, event):
        self.ShowButtons(True)
        event.Skip()
        
    def OnLeave(self, event):
        if self.Highlight != HIGHLIGHT_RESIZE or self.CanvasStartSize is None:
            x, y = event.GetPosition()
            width, height = self.GetSize()
            if (x <= 0 or x >= width - 1 or
                y <= 0 or y >= height - 1):
                self.ShowButtons(False)
        event.Skip()
    
    def OnCloseButton(self):
        wx.CallAfter(self.ParentWindow.DeleteValue, self)
    
    def OnForceButton(self):
        wx.CallAfter(self.ForceValue, self.Items[0])
        
    def OnReleaseButton(self):
        wx.CallAfter(self.ReleaseValue, self.Items[0])
    
    def OnResizeWindow(self, event):
        wx.CallAfter(self.RefreshButtonsState, True)
        event.Skip()
    
    def OnMouseDragging(self, x, y):
        xw, yw = self.GetPosition()
        self.ParentWindow.RefreshHighlight(x + xw, y + yw)
    
    def OnDragging(self, x, y):
        width, height = self.GetSize()
        if y < height / 2:
            if self.ParentWindow.IsViewerFirst(self):
                self.SetHighlight(HIGHLIGHT_BEFORE)
            else:
                self.SetHighlight(HIGHLIGHT_NONE)
                self.ParentWindow.HighlightPreviousViewer(self)
        else:
            self.SetHighlight(HIGHLIGHT_AFTER)
    
    def OnEraseBackground(self, event):
        pass
    
    def OnResize(self, event):
        wx.CallAfter(self.RefreshButtonsState, True)
        event.Skip()
    
    def ForceValue(self, item):
        iec_path = item.GetVariable()
        iec_type = self.ParentWindow.GetDataType(iec_path)
        if iec_type is not None:
            dialog = ForceVariableDialog(self, iec_type, str(item.GetValue()))
            if dialog.ShowModal() == wx.ID_OK:
                self.ParentWindow.ForceDataValue(iec_path.upper(), dialog.GetValue())
    
    def ReleaseValue(self, item):
        iec_path = item.GetVariable().upper()
        self.ParentWindow.ReleaseDataValue(iec_path)


class DebugVariableText(DebugVariableViewer, wx.Panel):
    
    def __init__(self, parent, window, items=[]):
        DebugVariableViewer.__init__(self, window, items)
        
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.SetDropTarget(DebugVariableDropTarget(window, self))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        
        self.SetMinSize(wx.Size(0, 25))
        
        self.Buttons.append(
            GraphButton(0, 0, GetBitmap("force"), self.OnForceButton))
        self.Buttons.append(
            GraphButton(0, 0, GetBitmap("release"), self.OnReleaseButton))
        self.Buttons.append(
            GraphButton(0, 0, GetBitmap("delete_graph"), self.OnCloseButton))
        
        self.ShowButtons(False)
        
    def RefreshViewer(self):
        width, height = self.GetSize()
        bitmap = wx.EmptyBitmap(width, height)
        
        dc = wx.BufferedDC(wx.ClientDC(self), bitmap)
        dc.Clear()
        dc.BeginDrawing()
        
        gc = wx.GCDC(dc)
        
        item_name = self.Items[0].GetVariable(self.ParentWindow.GetVariableNameMask())
        w, h = gc.GetTextExtent(item_name)
        gc.DrawText(item_name, 20, (height - h) / 2)
        
        if self.Items[0].IsForced():
            gc.SetTextForeground(wx.BLUE)
            self.Buttons[0].Disable()
            self.Buttons[1].Enable()
        else:
            self.Buttons[1].Disable()
            self.Buttons[0].Enable()
        self.RefreshButtonsState(True)
        
        item_value = self.Items[0].GetValue()
        w, h = gc.GetTextExtent(item_value)
        gc.DrawText(item_value, width - 40 - w, (height - h) / 2)
        
        self.DrawCommonElements(gc)
        
        gc.EndDrawing()
    
    def OnLeftDown(self, event):
        width, height = self.GetSize()
        item_name = self.Items[0].GetVariable(self.ParentWindow.GetVariableNameMask())
        w, h = self.GetTextExtent(item_name)
        x, y = event.GetPosition()
        rect = wx.Rect(20, (height - h) / 2, w, h)
        if rect.InsideXY(x, y):
            data = wx.TextDataObject(str((self.Items[0].GetVariable(), "debug", "move")))
            dragSource = wx.DropSource(self)
            dragSource.SetData(data)
            dragSource.DoDragDrop()
        else:
            event.Skip()
    
    def OnLeftUp(self, event):
        x, y = event.GetPosition()
        wx.CallAfter(self.HandleButtons, x, y)
        event.Skip()
    
    def OnPaint(self, event):
        self.RefreshViewer()
        event.Skip()

class DebugVariableGraphic(DebugVariableViewer, FigureCanvas):
    
    def __init__(self, parent, window, items, graph_type):
        DebugVariableViewer.__init__(self, window, items)
        
        self.CanvasSize = SIZE_MINI
        self.GraphType = graph_type
        self.CursorTick = None
        self.MouseStartPos = None
        self.StartCursorTick = None
        self.CanvasStartSize = None
        self.ContextualButtons = []
        self.ContextualButtonsItem = None
        
        self.Figure = matplotlib.figure.Figure(facecolor='w')
        self.Figure.subplotpars.update(top=0.95, left=0.1, bottom=0.1, right=0.95)
        
        FigureCanvas.__init__(self, parent, -1, self.Figure)
        self.SetWindowStyle(wx.WANTS_CHARS)
        self.SetBackgroundColour(wx.WHITE)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
        canvas_size = self.GetCanvasMinSize()
        self.SetMinSize(canvas_size)
        self.SetDropTarget(DebugVariableDropTarget(self.ParentWindow, self))
        self.mpl_connect('button_press_event', self.OnCanvasButtonPressed)
        self.mpl_connect('motion_notify_event', self.OnCanvasMotion)
        self.mpl_connect('button_release_event', self.OnCanvasButtonReleased)
        self.mpl_connect('scroll_event', self.OnCanvasScroll)
        
        for size, bitmap in zip([SIZE_MINI, SIZE_MIDDLE, SIZE_MAXI],
                                ["minimize_graph", "middle_graph", "maximize_graph"]):
            self.Buttons.append(GraphButton(0, 0, GetBitmap(bitmap), self.GetOnChangeSizeButton(size)))
        self.Buttons.append(
            GraphButton(0, 0, GetBitmap("export_graph_mini"), self.OnExportGraphButton))
        self.Buttons.append(
            GraphButton(0, 0, GetBitmap("delete_graph"), self.OnCloseButton))
        
        self.ResetGraphics()
        self.RefreshLabelsPosition(canvas_size.height)
        self.ShowButtons(False)
    
    def draw(self, drawDC=None):
        FigureCanvasAgg.draw(self)

        self.bitmap = _convert_agg_to_wx_bitmap(self.get_renderer(), None)
        self.bitmap.UseAlpha() 
        width, height = self.GetSize()
        bbox = self.GetAxesBoundingBox()
        
        destDC = wx.MemoryDC()
        destDC.SelectObject(self.bitmap)
        
        destGC = wx.GCDC(destDC)
        
        destGC.BeginDrawing()
        if self.Highlight == HIGHLIGHT_RESIZE:
            destGC.SetPen(HIGHLIGHT_RESIZE_PEN)
            destGC.SetBrush(HIGHLIGHT_RESIZE_BRUSH)
            destGC.DrawRectangle(0, height - 5, width, 5)
        else:
            destGC.SetPen(HIGHLIGHT_DROP_PEN)
            destGC.SetBrush(HIGHLIGHT_DROP_BRUSH)
            if self.Highlight == HIGHLIGHT_LEFT:
                destGC.DrawRectangle(bbox.x, bbox.y, 
                                     bbox.width / 2, bbox.height)
            elif self.Highlight == HIGHLIGHT_RIGHT:
                destGC.DrawRectangle(bbox.x + bbox.width / 2, bbox.y, 
                                     bbox.width / 2, bbox.height)
        
        self.DrawCommonElements(destGC, self.Buttons + self.ContextualButtons)
        
        destGC.EndDrawing()
        
        self._isDrawn = True
        self.gui_repaint(drawDC=drawDC)
    
    def GetButtons(self):
        return self.Buttons + self.ContextualButtons
    
    def PopupContextualButtons(self, item, rect, style=wx.RIGHT):
        if self.ContextualButtonsItem is not None and item != self.ContextualButtonsItem:
            self.DismissContextualButtons()
        
        if self.ContextualButtonsItem is None:
            self.ContextualButtonsItem = item
            
            if self.ContextualButtonsItem.IsForced():
                self.ContextualButtons.append(
                    GraphButton(0, 0, GetBitmap("release"), self.OnReleaseButton))
            self.ContextualButtons.append(
                GraphButton(0, 0, GetBitmap("force"), self.OnForceButton))
            self.ContextualButtons.append(
                GraphButton(0, 0, GetBitmap("export_graph_mini"), self.OnExportItemGraphButton))
            self.ContextualButtons.append(
                GraphButton(0, 0, GetBitmap("delete_graph"), self.OnRemoveItemButton))
            
            offset = 0
            buttons = self.ContextualButtons[:]
            if style in [wx.TOP, wx.LEFT]:
                 buttons.reverse()
            for button in buttons:
                w, h = button.GetSize()
                if style in [wx.LEFT, wx.RIGHT]:
                    if style == wx.LEFT:
                        x = rect.x - w - offset
                    else:
                        x = rect.x + rect.width + offset
                    y = rect.y + (rect.height - h) / 2
                    offset += w
                else:
                    x = rect.x + (rect.width - w ) / 2
                    if style == wx.TOP:
                        y = rect.y - h - offset
                    else:
                        y = rect.y + rect.height + offset
                    offset += h
                button.SetPosition(x, y)
            self.ParentWindow.ForceRefresh()
    
    def DismissContextualButtons(self):
        if self.ContextualButtonsItem is not None:
            self.ContextualButtonsItem = None
            self.ContextualButtons = []
            self.ParentWindow.ForceRefresh()
    
    def IsOverContextualButton(self, x, y):
        for button in self.ContextualButtons:
            if button.HitTest(x, y):
                return True
        return False
    
    def SetMinSize(self, size):
        wx.Window.SetMinSize(self, size)
        wx.CallAfter(self.RefreshButtonsState)
    
    def GetOnChangeSizeButton(self, size):
        def OnChangeSizeButton():
            self.CanvasSize = size
            self.SetCanvasSize(200, self.CanvasSize)
        return OnChangeSizeButton
    
    def OnExportGraphButton(self):
        self.ExportGraph()
    
    def OnForceButton(self):
        wx.CallAfter(self.ForceValue, 
                     self.ContextualButtonsItem)
        self.DismissContextualButtons()
        
    def OnReleaseButton(self):
        wx.CallAfter(self.ReleaseValue, 
                     self.ContextualButtonsItem)
        self.DismissContextualButtons()
    
    def OnExportItemGraphButton(self):
        wx.CallAfter(self.ExportGraph, 
                     self.ContextualButtonsItem)
        self.DismissContextualButtons()
        
    def OnRemoveItemButton(self):            
        wx.CallAfter(self.ParentWindow.DeleteValue, self, 
                     self.ContextualButtonsItem)
        self.DismissContextualButtons()
    
    def RefreshLabelsPosition(self, height):
        canvas_ratio = 1. / height
        graph_ratio = 1. / ((1.0 - (CANVAS_BORDER[0] + CANVAS_BORDER[1]) * canvas_ratio) * height)
        
        self.Figure.subplotpars.update(
            top= 1.0 - CANVAS_BORDER[1] * canvas_ratio, 
            bottom= CANVAS_BORDER[0] * canvas_ratio)
        
        if self.GraphType == GRAPH_PARALLEL or self.Is3DCanvas():
            num_item = len(self.Items)
            for idx in xrange(num_item):
                if not self.Is3DCanvas():
                    self.AxesLabels[idx].set_position(
                        (0.05, 
                         1.0 - (CANVAS_PADDING + AXES_LABEL_HEIGHT * idx) * graph_ratio))
                self.Labels[idx].set_position(
                    (0.95, 
                     CANVAS_PADDING * graph_ratio + 
                     (num_item - idx - 1) * VALUE_LABEL_HEIGHT * graph_ratio))
        else:
            self.AxesLabels[0].set_position((0.1, CANVAS_PADDING * graph_ratio))
            self.Labels[0].set_position((0.95, CANVAS_PADDING * graph_ratio))
            self.AxesLabels[1].set_position((0.05, 2 * CANVAS_PADDING * graph_ratio))
            self.Labels[1].set_position((0.05, 1.0 - CANVAS_PADDING * graph_ratio))
    
        self.Figure.subplots_adjust()
    
    def GetCanvasMinSize(self):
        return wx.Size(200, 
                       CANVAS_BORDER[0] + CANVAS_BORDER[1] + 
                       2 * CANVAS_PADDING + VALUE_LABEL_HEIGHT * len(self.Items))
    
    def SetCanvasSize(self, width, height):
        height = max(height, self.GetCanvasMinSize()[1])
        self.SetMinSize(wx.Size(width, height))
        self.RefreshLabelsPosition(height)
        self.RefreshButtonsState()
        self.ParentWindow.RefreshGraphicsSizer()
        
    def GetAxesBoundingBox(self, absolute=False):
        width, height = self.GetSize()
        ax, ay, aw, ah = self.figure.gca().get_position().bounds
        bbox = wx.Rect(ax * width, height - (ay + ah) * height - 1,
                       aw * width + 2, ah * height + 1)
        if absolute:
            xw, yw = self.GetPosition()
            bbox.x += xw
            bbox.y += yw
        return bbox
    
    def OnCanvasButtonPressed(self, event):
        width, height = self.GetSize()
        x, y = event.x, height - event.y
        if not self.IsOverButton(x, y):
            if event.inaxes == self.Axes:
                item_idx = None
                for i, t in ([pair for pair in enumerate(self.AxesLabels)] + 
                             [pair for pair in enumerate(self.Labels)]):
                    (x0, y0), (x1, y1) = t.get_window_extent().get_points()
                    rect = wx.Rect(x0, height - y1, x1 - x0, y1 - y0)
                    if rect.InsideXY(x, y):
                        item_idx = i
                        break
                if item_idx is not None:
                    self.ShowButtons(False)
                    self.DismissContextualButtons()
                    xw, yw = self.GetPosition()
                    self.ParentWindow.StartDragNDrop(self, 
                        self.Items[item_idx], x + xw, y + yw, x + xw, y + yw)
                elif not self.Is3DCanvas():
                    self.MouseStartPos = wx.Point(x, y)
                    if event.button == 1 and event.inaxes == self.Axes:
                        self.StartCursorTick = self.CursorTick
                        self.HandleCursorMove(event)
                    elif event.button == 2 and self.GraphType == GRAPH_PARALLEL:
                        width, height = self.GetSize()
                        start_tick, end_tick = self.ParentWindow.GetRange()
                        self.StartCursorTick = start_tick
            
            elif event.button == 1 and event.y <= 5:
                self.MouseStartPos = wx.Point(x, y)
                self.CanvasStartSize = self.GetSize()
    
    def OnCanvasButtonReleased(self, event):
        if self.ParentWindow.IsDragging():
            width, height = self.GetSize()
            xw, yw = self.GetPosition()
            self.ParentWindow.StopDragNDrop(
                self.ParentWindow.DraggingAxesPanel.Items[0].GetVariable(),
                xw + event.x, 
                yw + height - event.y)
        else:
            self.MouseStartPos = None
            self.StartCursorTick = None
            self.CanvasStartSize = None
            width, height = self.GetSize()
            self.HandleButtons(event.x, height - event.y)
            if event.y > 5 and self.SetHighlight(HIGHLIGHT_NONE):
                self.SetCursor(wx.NullCursor)
                self.ParentWindow.ForceRefresh()
    
    def OnCanvasMotion(self, event):
        width, height = self.GetSize()
        if self.ParentWindow.IsDragging():
            xw, yw = self.GetPosition()
            self.ParentWindow.MoveDragNDrop(
                xw + event.x, 
                yw + height - event.y)
        else:
            if not self.Is3DCanvas():
                if event.button == 1 and self.CanvasStartSize is None:
                    if event.inaxes == self.Axes:
                        if self.MouseStartPos is not None:
                            self.HandleCursorMove(event)
                    elif self.MouseStartPos is not None and len(self.Items) == 1:
                        xw, yw = self.GetPosition()
                        self.ParentWindow.SetCursorTick(self.StartCursorTick)
                        self.ParentWindow.StartDragNDrop(self, 
                            self.Items[0],
                            event.x + xw, height - event.y + yw, 
                            self.MouseStartPos.x + xw, self.MouseStartPos.y + yw)
                elif event.button == 2 and self.GraphType == GRAPH_PARALLEL and self.MouseStartPos is not None:
                    start_tick, end_tick = self.ParentWindow.GetRange()
                    rect = self.GetAxesBoundingBox()
                    self.ParentWindow.SetCanvasPosition(
                        self.StartCursorTick + (self.MouseStartPos.x - event.x) *
                        (end_tick - start_tick) / rect.width)    
            
            if event.button == 1 and self.CanvasStartSize is not None:
                width, height = self.GetSize()
                self.SetCanvasSize(width, 
                    self.CanvasStartSize.height + height - event.y - self.MouseStartPos.y)
                
            elif event.button in [None, "up", "down"]:
                if self.GraphType == GRAPH_PARALLEL:
                    orientation = [wx.RIGHT] * len(self.AxesLabels) + [wx.LEFT] * len(self.Labels)
                elif len(self.AxesLabels) > 0:
                    orientation = [wx.RIGHT, wx.TOP, wx.LEFT, wx.BOTTOM]
                else:
                    orientation = [wx.LEFT] * len(self.Labels)
                item_idx = None
                item_style = None
                for (i, t), style in zip([pair for pair in enumerate(self.AxesLabels)] + 
                                         [pair for pair in enumerate(self.Labels)], 
                                         orientation):
                    (x0, y0), (x1, y1) = t.get_window_extent().get_points()
                    rect = wx.Rect(x0, height - y1, x1 - x0, y1 - y0)
                    if rect.InsideXY(event.x, height - event.y):
                        item_idx = i
                        item_style = style
                        break
                if item_idx is not None:
                    self.PopupContextualButtons(self.Items[item_idx], rect, item_style)
                    return 
                if not self.IsOverContextualButton(event.x, height - event.y):
                    self.DismissContextualButtons()
                
                if event.y <= 5:
                    if self.SetHighlight(HIGHLIGHT_RESIZE):
                        self.SetCursor(wx.StockCursor(wx.CURSOR_SIZENS))
                        self.ParentWindow.ForceRefresh()
                else:
                    if self.SetHighlight(HIGHLIGHT_NONE):
                        self.SetCursor(wx.NullCursor)
                        self.ParentWindow.ForceRefresh()
    
    def OnCanvasScroll(self, event):
        if event.inaxes is not None and event.guiEvent.ControlDown():
            if self.GraphType == GRAPH_ORTHOGONAL:
                start_tick, end_tick = self.ParentWindow.GetRange()
                tick = (start_tick + end_tick) / 2.
            else:
                tick = event.xdata
            self.ParentWindow.ChangeRange(int(-event.step) / 3, tick)
            self.ParentWindow.VetoScrollEvent = True
    
    def OnDragging(self, x, y):
        width, height = self.GetSize()
        bbox = self.GetAxesBoundingBox()
        if bbox.InsideXY(x, y) and not self.Is3DCanvas():
            rect = wx.Rect(bbox.x, bbox.y, bbox.width / 2, bbox.height)
            if rect.InsideXY(x, y):
                self.SetHighlight(HIGHLIGHT_LEFT)
            else:
                self.SetHighlight(HIGHLIGHT_RIGHT)
        elif y < height / 2:
            if self.ParentWindow.IsViewerFirst(self):
                self.SetHighlight(HIGHLIGHT_BEFORE)
            else:
                self.SetHighlight(HIGHLIGHT_NONE)
                self.ParentWindow.HighlightPreviousViewer(self)
        else:
            self.SetHighlight(HIGHLIGHT_AFTER)
    
    def OnLeave(self, event):
        if self.CanvasStartSize is None and self.SetHighlight(HIGHLIGHT_NONE):
            self.SetCursor(wx.NullCursor)
            self.ParentWindow.ForceRefresh()
        DebugVariableViewer.OnLeave(self, event)
    
    KEY_CURSOR_INCREMENT = {
        wx.WXK_LEFT: -1,
        wx.WXK_RIGHT: 1,
        wx.WXK_UP: -10,
        wx.WXK_DOWN: 10}
    def OnKeyDown(self, event):
        if self.CursorTick is not None:
            move = self.KEY_CURSOR_INCREMENT.get(event.GetKeyCode(), None)
            if move is not None:
                self.ParentWindow.MoveCursorTick(move)
        event.Skip()
    
    def HandleCursorMove(self, event):
        start_tick, end_tick = self.ParentWindow.GetRange()
        cursor_tick = None
        if self.GraphType == GRAPH_ORTHOGONAL:
            x_data = self.Items[0].GetData(start_tick, end_tick)
            y_data = self.Items[1].GetData(start_tick, end_tick)
            if len(x_data) > 0 and len(y_data) > 0:
                length = min(len(x_data), len(y_data))
                d = numpy.sqrt((x_data[:length,1]-event.xdata) ** 2 + (y_data[:length,1]-event.ydata) ** 2)
                cursor_tick = x_data[numpy.argmin(d), 0]
        else:
            data = self.Items[0].GetData(start_tick, end_tick)
            if len(data) > 0:
                cursor_tick = data[numpy.argmin(numpy.abs(data[:,0] - event.xdata)), 0]
        if cursor_tick is not None:
            self.ParentWindow.SetCursorTick(cursor_tick)
    
    def OnAxesMotion(self, event):
        if self.Is3DCanvas():
            current_time = gettime()
            if current_time - self.LastMotionTime > REFRESH_PERIOD:
                self.LastMotionTime = current_time
                Axes3D._on_move(self.Axes, event)
    
    def ResetGraphics(self):
        self.Figure.clear()
        if self.Is3DCanvas():
            self.Axes = self.Figure.gca(projection='3d')
            self.Axes.set_color_cycle(['b'])
            self.LastMotionTime = gettime()
            setattr(self.Axes, "_on_move", self.OnAxesMotion)
            self.Axes.mouse_init()
            self.Axes.tick_params(axis='z', labelsize='small')
        else:
            self.Axes = self.Figure.gca()
            self.Axes.set_color_cycle(color_cycle)
        self.Axes.tick_params(axis='x', labelsize='small')
        self.Axes.tick_params(axis='y', labelsize='small')
        self.Plots = []
        self.VLine = None
        self.HLine = None
        self.Labels = []
        self.AxesLabels = []
        if not self.Is3DCanvas():
            text_func = self.Axes.text
        else:
            text_func = self.Axes.text2D
        if self.GraphType == GRAPH_PARALLEL or self.Is3DCanvas():
            num_item = len(self.Items)
            for idx in xrange(num_item):
                if num_item == 1:
                    color = 'k'
                else:
                    color = color_cycle[idx % len(color_cycle)]
                if not self.Is3DCanvas():
                    self.AxesLabels.append(
                        text_func(0, 0, "", size='small',
                                  verticalalignment='top', 
                                  color=color,
                                  transform=self.Axes.transAxes))
                self.Labels.append(
                    text_func(0, 0, "", size='large', 
                              horizontalalignment='right',
                              color=color,
                              transform=self.Axes.transAxes))
        else:
            self.AxesLabels.append(
                self.Axes.text(0, 0, "", size='small',
                               transform=self.Axes.transAxes))
            self.Labels.append(
                self.Axes.text(0, 0, "", size='large',
                               horizontalalignment='right',
                               transform=self.Axes.transAxes))
            self.AxesLabels.append(
                self.Axes.text(0, 0, "", size='small',
                               rotation='vertical',
                               verticalalignment='bottom',
                               transform=self.Axes.transAxes))
            self.Labels.append(
                self.Axes.text(0, 0, "", size='large',
                               rotation='vertical',
                               verticalalignment='top',
                               transform=self.Axes.transAxes))
        width, height = self.GetSize()
        self.RefreshLabelsPosition(height)
        
    def AddItem(self, item):
        DebugVariableViewer.AddItem(self, item)
        self.ResetGraphics()
        
    def RemoveItem(self, item):
        DebugVariableViewer.RemoveItem(self, item)
        if not self.IsEmpty():
            if len(self.Items) == 1:
                self.GraphType = GRAPH_PARALLEL
            self.ResetGraphics()
    
    def UnregisterObsoleteData(self):
        DebugVariableViewer.UnregisterObsoleteData(self)
        if not self.IsEmpty():
            self.ResetGraphics()
    
    def Is3DCanvas(self):
        return self.GraphType == GRAPH_ORTHOGONAL and len(self.Items) == 3
    
    def SetCursorTick(self, cursor_tick):
        self.CursorTick = cursor_tick
        
    def RefreshViewer(self, refresh_graphics=True):
        
        if refresh_graphics:
            start_tick, end_tick = self.ParentWindow.GetRange()
            
            if self.GraphType == GRAPH_PARALLEL:    
                min_value = max_value = None
                
                for idx, item in enumerate(self.Items):
                    data = item.GetData(start_tick, end_tick)
                    if data is not None:
                        item_min_value, item_max_value = item.GetValueRange()
                        if min_value is None:
                            min_value = item_min_value
                        elif item_min_value is not None:
                            min_value = min(min_value, item_min_value)
                        if max_value is None:
                            max_value = item_max_value
                        elif item_max_value is not None:
                            max_value = max(max_value, item_max_value)
                        
                        if len(self.Plots) <= idx:
                            self.Plots.append(
                                self.Axes.plot(data[:, 0], data[:, 1])[0])
                        else:
                            self.Plots[idx].set_data(data[:, 0], data[:, 1])
                    
                if min_value is not None and max_value is not None:
                    y_center = (min_value + max_value) / 2.
                    y_range = max(1.0, max_value - min_value)
                else:
                    y_center = 0.5
                    y_range = 1.0
                x_min, x_max = start_tick, end_tick
                y_min, y_max = y_center - y_range * 0.55, y_center + y_range * 0.55
                
                if self.CursorTick is not None and start_tick <= self.CursorTick <= end_tick:
                    if self.VLine is None:
                        self.VLine = self.Axes.axvline(self.CursorTick, color=cursor_color)
                    else:
                        self.VLine.set_xdata((self.CursorTick, self.CursorTick))
                    self.VLine.set_visible(True)
                else:
                    if self.VLine is not None:
                        self.VLine.set_visible(False)
            else:
                min_start_tick = reduce(max, [item.GetData()[0, 0] 
                                              for item in self.Items
                                              if len(item.GetData()) > 0], 0)
                start_tick = max(start_tick, min_start_tick)
                end_tick = max(end_tick, min_start_tick)
                x_data, x_min, x_max = OrthogonalData(self.Items[0], start_tick, end_tick)
                y_data, y_min, y_max = OrthogonalData(self.Items[1], start_tick, end_tick)
                if self.CursorTick is not None:
                    x_cursor, x_forced = self.Items[0].GetValue(self.CursorTick, raw=True)
                    y_cursor, y_forced = self.Items[1].GetValue(self.CursorTick, raw=True)
                length = 0
                if x_data is not None and y_data is not None:  
                    length = min(len(x_data), len(y_data))
                if len(self.Items) < 3:
                    if x_data is not None and y_data is not None:
                        if len(self.Plots) == 0:
                            self.Plots.append(
                                self.Axes.plot(x_data[:, 1][:length], 
                                               y_data[:, 1][:length])[0])
                        else:
                            self.Plots[0].set_data(
                                x_data[:, 1][:length], 
                                y_data[:, 1][:length])
                    
                    if self.CursorTick is not None and start_tick <= self.CursorTick <= end_tick:
                        if self.VLine is None:
                            self.VLine = self.Axes.axvline(x_cursor, color=cursor_color)
                        else:
                            self.VLine.set_xdata((x_cursor, x_cursor))
                        if self.HLine is None:
                            self.HLine = self.Axes.axhline(y_cursor, color=cursor_color)
                        else:
                            self.HLine.set_ydata((y_cursor, y_cursor))
                        self.VLine.set_visible(True)
                        self.HLine.set_visible(True)
                    else:
                        if self.VLine is not None:
                            self.VLine.set_visible(False)
                        if self.HLine is not None:
                            self.HLine.set_visible(False)
                else:
                    while len(self.Axes.lines) > 0:
                        self.Axes.lines.pop()
                    z_data, z_min, z_max = OrthogonalData(self.Items[2], start_tick, end_tick)
                    if self.CursorTick is not None:
                        z_cursor, z_forced = self.Items[2].GetValue(self.CursorTick, raw=True)
                    if x_data is not None and y_data is not None and z_data is not None:
                        length = min(length, len(z_data))
                        self.Axes.plot(x_data[:, 1][:length],
                                       y_data[:, 1][:length],
                                       zs = z_data[:, 1][:length])
                    self.Axes.set_zlim(z_min, z_max)
                    if self.CursorTick is not None and start_tick <= self.CursorTick <= end_tick:
                        for kwargs in [{"xs": numpy.array([x_min, x_max])},
                                       {"ys": numpy.array([y_min, y_max])},
                                       {"zs": numpy.array([z_min, z_max])}]:
                            for param, value in [("xs", numpy.array([x_cursor, x_cursor])),
                                                 ("ys", numpy.array([y_cursor, y_cursor])),
                                                 ("zs", numpy.array([z_cursor, z_cursor]))]:
                                kwargs.setdefault(param, value)
                            kwargs["color"] = cursor_color
                            self.Axes.plot(**kwargs)
                
            self.Axes.set_xlim(x_min, x_max)
            self.Axes.set_ylim(y_min, y_max)
        
        variable_name_mask = self.ParentWindow.GetVariableNameMask()
        if self.CursorTick is not None:
            values, forced = apply(zip, [item.GetValue(self.CursorTick) for item in self.Items])
        else:
            values, forced = apply(zip, [(item.GetValue(), item.IsForced()) for item in self.Items])
        labels = [item.GetVariable(variable_name_mask) for item in self.Items]
        styles = map(lambda x: {True: 'italic', False: 'normal'}[x], forced)
        if self.Is3DCanvas():
            for idx, label_func in enumerate([self.Axes.set_xlabel, 
                                              self.Axes.set_ylabel,
                                              self.Axes.set_zlabel]):
                label_func(labels[idx], fontdict={'size': 'small','color': color_cycle[idx]})
        else:
            for label, text in zip(self.AxesLabels, labels):
                label.set_text(text)
        for label, value, style in zip(self.Labels, values, styles):
            label.set_text(value)
            label.set_style(style)
        
        self.draw()

    def ExportGraph(self, item=None):
        if item is not None:
            variables = [(item, [entry for entry in item.GetData()])]
        else:
            variables = [(item, [entry for entry in item.GetData()])
                         for item in self.Items]
        self.ParentWindow.CopyDataToClipboard(variables)
    
class DebugVariableGraphicPanel(wx.Panel, DebugViewer):
    
    def __init__(self, parent, producer, window):
        wx.Panel.__init__(self, parent, style=wx.SP_3D|wx.TAB_TRAVERSAL)
        
        self.ParentWindow = window
        
        self.HasNewData = False
        self.Force = False
        
        self.SetBackgroundColour(wx.WHITE)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Ticks = numpy.array([])
        self.StartTick = 0
        self.Fixed = False
        self.CursorTick = None
        self.DraggingAxesPanel = None
        self.DraggingAxesBoundingBox = None
        self.DraggingAxesMousePos = None
        self.VetoScrollEvent = False
        self.VariableNameMask = []
        
        self.GraphicPanels = []
        
        graphics_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.AddSizer(graphics_button_sizer, border=5, flag=wx.GROW|wx.ALL)
        
        range_label = wx.StaticText(self, label=_('Range:'))
        graphics_button_sizer.AddWindow(range_label, flag=wx.ALIGN_CENTER_VERTICAL)
        
        self.CanvasRange = wx.ComboBox(self, style=wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.OnRangeChanged, self.CanvasRange)
        graphics_button_sizer.AddWindow(self.CanvasRange, 1, 
              border=5, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        
        self.CanvasRange.Clear()
        default_range_idx = 0
        for idx, (text, value) in enumerate(RANGE_VALUES):
            self.CanvasRange.Append(text)
            if text == "1s":
                default_range_idx = idx
        self.CanvasRange.SetSelection(default_range_idx)
        
        for name, bitmap, help in [
            ("CurrentButton", "current", _("Go to current value")),
            ("ExportGraphButton", "export_graph", _("Export graph values to clipboard"))]:
            button = wx.lib.buttons.GenBitmapButton(self, 
                  bitmap=GetBitmap(bitmap), 
                  size=wx.Size(28, 28), style=wx.NO_BORDER)
            button.SetToolTipString(help)
            setattr(self, name, button)
            self.Bind(wx.EVT_BUTTON, getattr(self, "On" + name), button)
            graphics_button_sizer.AddWindow(button, border=5, flag=wx.LEFT)
        
        self.CanvasPosition = wx.ScrollBar(self, 
              size=wx.Size(0, 16), style=wx.SB_HORIZONTAL)
        self.CanvasPosition.Bind(wx.EVT_SCROLL_THUMBTRACK, 
              self.OnPositionChanging, self.CanvasPosition)
        self.CanvasPosition.Bind(wx.EVT_SCROLL_LINEUP, 
              self.OnPositionChanging, self.CanvasPosition)
        self.CanvasPosition.Bind(wx.EVT_SCROLL_LINEDOWN, 
              self.OnPositionChanging, self.CanvasPosition)
        self.CanvasPosition.Bind(wx.EVT_SCROLL_PAGEUP, 
              self.OnPositionChanging, self.CanvasPosition)
        self.CanvasPosition.Bind(wx.EVT_SCROLL_PAGEDOWN, 
              self.OnPositionChanging, self.CanvasPosition)
        main_sizer.AddWindow(self.CanvasPosition, border=5, flag=wx.GROW|wx.LEFT|wx.RIGHT|wx.BOTTOM)
        
        self.TickSizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.AddSizer(self.TickSizer, border=5, flag=wx.ALL|wx.GROW)
        
        self.TickLabel = wx.StaticText(self)
        self.TickSizer.AddWindow(self.TickLabel, border=5, flag=wx.RIGHT)
        
        self.MaskLabel = wx.TextCtrl(self, style=wx.TE_READONLY|wx.TE_CENTER|wx.NO_BORDER)
        self.TickSizer.AddWindow(self.MaskLabel, 1, border=5, flag=wx.RIGHT|wx.GROW)
        
        self.TickTimeLabel = wx.StaticText(self)
        self.TickSizer.AddWindow(self.TickTimeLabel)
        
        self.GraphicsWindow = wx.ScrolledWindow(self, style=wx.HSCROLL|wx.VSCROLL)
        self.GraphicsWindow.SetBackgroundColour(wx.WHITE)
        self.GraphicsWindow.SetDropTarget(DebugVariableDropTarget(self))
        self.GraphicsWindow.Bind(wx.EVT_ERASE_BACKGROUND, self.OnGraphicsWindowEraseBackground)
        self.GraphicsWindow.Bind(wx.EVT_PAINT, self.OnGraphicsWindowPaint)
        self.GraphicsWindow.Bind(wx.EVT_SIZE, self.OnGraphicsWindowResize)
        self.GraphicsWindow.Bind(wx.EVT_MOUSEWHEEL, self.OnGraphicsWindowMouseWheel)
        
        main_sizer.AddWindow(self.GraphicsWindow, 1, flag=wx.GROW)
        
        self.GraphicsSizer = wx.BoxSizer(wx.VERTICAL)
        self.GraphicsWindow.SetSizer(self.GraphicsSizer)
    
        DebugViewer.__init__(self, producer, True)
        
        self.SetSizer(main_sizer)
    
    def SetTickTime(self, ticktime=0):
        self.Ticktime = ticktime
        if self.Ticktime == 0:
            self.Ticktime = MILLISECOND
        self.CurrentRange = RANGE_VALUES[
            self.CanvasRange.GetSelection()][1] / self.Ticktime
    
    def SetDataProducer(self, producer):
        DebugViewer.SetDataProducer(self, producer)
        
        if self.DataProducer is not None:
            self.SetTickTime(self.DataProducer.GetTicktime())
    
    def RefreshNewData(self, *args, **kwargs):
        if self.HasNewData or self.Force:
            self.HasNewData = False
            self.RefreshView()
        DebugViewer.RefreshNewData(self, *args, **kwargs)
    
    def NewDataAvailable(self, tick, *args, **kwargs):
        if tick is not None:
            if len(self.Ticks) == 0:
                self.StartTick = tick 
            self.Ticks = numpy.append(self.Ticks, [tick])
            if not self.Fixed or tick < self.StartTick + self.CurrentRange:
                self.StartTick = max(self.StartTick, tick - self.CurrentRange)
            if self.Fixed and self.Ticks[-1] - self.Ticks[0] < self.CurrentRange:
                self.Force = True
        DebugViewer.NewDataAvailable(self, tick, *args, **kwargs)
    
    def ForceRefresh(self):
        self.Force = True
        wx.CallAfter(self.NewDataAvailable, None, True)
    
    def RefreshGraphicsSizer(self):
        self.GraphicsSizer.Clear()
        
        for panel in self.GraphicPanels:
            self.GraphicsSizer.AddWindow(panel, flag=wx.GROW)
            
        self.GraphicsSizer.Layout()
        self.RefreshGraphicsWindowScrollbars()
    
    def SetCanvasPosition(self, tick):
        tick = max(self.Ticks[0], min(tick, self.Ticks[-1] - self.CurrentRange))
        self.StartTick = self.Ticks[numpy.argmin(numpy.abs(self.Ticks - tick))]
        self.Fixed = True
        self.RefreshCanvasPosition()
        self.ForceRefresh()
    
    def SetCursorTick(self, cursor_tick):
        self.CursorTick = cursor_tick
        self.Fixed = True
        self.UpdateCursorTick() 
    
    def MoveCursorTick(self, move):
        if self.CursorTick is not None:
            cursor_tick = max(self.Ticks[0], 
                          min(self.CursorTick + move, 
                              self.Ticks[-1]))
            cursor_tick_idx = numpy.argmin(numpy.abs(self.Ticks - cursor_tick))
            if self.Ticks[cursor_tick_idx] == self.CursorTick:
                cursor_tick_idx = max(0, 
                                  min(cursor_tick_idx + abs(move) / move, 
                                      len(self.Ticks) - 1))
            self.CursorTick = self.Ticks[cursor_tick_idx]
            self.StartTick = max(self.Ticks[
                                numpy.argmin(numpy.abs(self.Ticks - 
                                        self.CursorTick + self.CurrentRange))],
                             min(self.StartTick, self.CursorTick))
            self.RefreshCanvasPosition()
            self.UpdateCursorTick() 
            
    def ResetCursorTick(self):
        self.CursorTick = None
        self.UpdateCursorTick()
    
    def UpdateCursorTick(self):
        for panel in self.GraphicPanels:
            if isinstance(panel, DebugVariableGraphic):
                panel.SetCursorTick(self.CursorTick)
        self.ForceRefresh()
    
    def StartDragNDrop(self, panel, item, x_mouse, y_mouse, x_mouse_start, y_mouse_start):
        if len(panel.GetItems()) > 1:
            self.DraggingAxesPanel = DebugVariableGraphic(self.GraphicsWindow, self, [item], GRAPH_PARALLEL)
            self.DraggingAxesPanel.SetCursorTick(self.CursorTick)
            width, height = panel.GetSize()
            self.DraggingAxesPanel.SetSize(wx.Size(width, height))
            self.DraggingAxesPanel.ResetGraphics()
            self.DraggingAxesPanel.SetPosition(wx.Point(0, -height))
        else:
            self.DraggingAxesPanel = panel
        self.DraggingAxesBoundingBox = panel.GetAxesBoundingBox(absolute=True)
        self.DraggingAxesMousePos = wx.Point(
            x_mouse_start - self.DraggingAxesBoundingBox.x, 
            y_mouse_start - self.DraggingAxesBoundingBox.y)
        self.MoveDragNDrop(x_mouse, y_mouse)
        
    def MoveDragNDrop(self, x_mouse, y_mouse):
        self.DraggingAxesBoundingBox.x = x_mouse - self.DraggingAxesMousePos.x
        self.DraggingAxesBoundingBox.y = y_mouse - self.DraggingAxesMousePos.y
        self.RefreshHighlight(x_mouse, y_mouse)
    
    def RefreshHighlight(self, x_mouse, y_mouse):
        for idx, panel in enumerate(self.GraphicPanels):
            x, y = panel.GetPosition()
            width, height = panel.GetSize()
            rect = wx.Rect(x, y, width, height)
            if (rect.InsideXY(x_mouse, y_mouse) or 
                idx == 0 and y_mouse < 0 or
                idx == len(self.GraphicPanels) - 1 and y_mouse > panel.GetPosition()[1]):
                panel.OnDragging(x_mouse - x, y_mouse - y)
            else:
                panel.SetHighlight(HIGHLIGHT_NONE)
        if wx.Platform == "__WXMSW__":
            self.RefreshView()
        else:
            self.ForceRefresh()
    
    def ResetHighlight(self):
        for panel in self.GraphicPanels:
            panel.SetHighlight(HIGHLIGHT_NONE)
        if wx.Platform == "__WXMSW__":
            self.RefreshView()
        else:
            self.ForceRefresh()
    
    def IsDragging(self):
        return self.DraggingAxesPanel is not None
    
    def GetDraggingAxesClippingRegion(self, panel):
        x, y = panel.GetPosition()
        width, height = panel.GetSize()
        bbox = wx.Rect(x, y, width, height)
        bbox = bbox.Intersect(self.DraggingAxesBoundingBox)
        bbox.x -= x
        bbox.y -= y
        return bbox
    
    def GetDraggingAxesPosition(self, panel):
        x, y = panel.GetPosition()
        return wx.Point(self.DraggingAxesBoundingBox.x - x,
                        self.DraggingAxesBoundingBox.y - y)
    
    def StopDragNDrop(self, variable, x_mouse, y_mouse):
        if self.DraggingAxesPanel not in self.GraphicPanels:
            self.DraggingAxesPanel.Destroy()
        self.DraggingAxesPanel = None
        self.DraggingAxesBoundingBox = None
        self.DraggingAxesMousePos = None
        for idx, panel in enumerate(self.GraphicPanels):
            panel.SetHighlight(HIGHLIGHT_NONE)
            xw, yw = panel.GetPosition()
            width, height = panel.GetSize()
            bbox = wx.Rect(xw, yw, width, height)
            if bbox.InsideXY(x_mouse, y_mouse):
                panel.ShowButtons(True)
                merge_type = GRAPH_PARALLEL
                if isinstance(panel, DebugVariableText) or panel.Is3DCanvas():
                    if y_mouse > yw + height / 2:
                        idx += 1
                    wx.CallAfter(self.MoveValue, variable, idx)
                else:
                    rect = panel.GetAxesBoundingBox(True)
                    if rect.InsideXY(x_mouse, y_mouse):
                        merge_rect = wx.Rect(rect.x, rect.y, rect.width / 2., rect.height)
                        if merge_rect.InsideXY(x_mouse, y_mouse):
                            merge_type = GRAPH_ORTHOGONAL
                        wx.CallAfter(self.MergeGraphs, variable, idx, merge_type, force=True)
                    else:
                        if y_mouse > yw + height / 2:
                            idx += 1
                        wx.CallAfter(self.MoveValue, variable, idx)
                self.ForceRefresh()
                return 
        width, height = self.GraphicsWindow.GetVirtualSize()
        rect = wx.Rect(0, 0, width, height)
        if rect.InsideXY(x_mouse, y_mouse):
            wx.CallAfter(self.MoveValue, variable, len(self.GraphicPanels))
        self.ForceRefresh()
    
    def RefreshView(self):
        self.RefreshCanvasPosition()
        
        width, height = self.GraphicsWindow.GetVirtualSize()
        bitmap = wx.EmptyBitmap(width, height)
        dc = wx.BufferedDC(wx.ClientDC(self.GraphicsWindow), bitmap)
        dc.Clear()
        dc.BeginDrawing()
        if self.DraggingAxesPanel is not None:
            destBBox = self.DraggingAxesBoundingBox
            srcBBox = self.DraggingAxesPanel.GetAxesBoundingBox()
            
            srcBmp = _convert_agg_to_wx_bitmap(self.DraggingAxesPanel.get_renderer(), None)
            srcDC = wx.MemoryDC()
            srcDC.SelectObject(srcBmp)
                
            dc.Blit(destBBox.x, destBBox.y, 
                    int(destBBox.width), int(destBBox.height), 
                    srcDC, srcBBox.x, srcBBox.y)
        dc.EndDrawing()
        
        if not self.Fixed or self.Force:
            self.Force = False
            refresh_graphics = True
        else:
            refresh_graphics = False
        
        if self.DraggingAxesPanel is not None and self.DraggingAxesPanel not in self.GraphicPanels:
            self.DraggingAxesPanel.RefreshViewer(refresh_graphics)
        for panel in self.GraphicPanels:
            if isinstance(panel, DebugVariableGraphic):
                panel.RefreshViewer(refresh_graphics)
            else:
                panel.RefreshViewer()
        
        if self.CursorTick is not None:
            tick = self.CursorTick
        elif len(self.Ticks) > 0:
            tick = self.Ticks[-1]
        else:
            tick = None
        if tick is not None:
            self.TickLabel.SetLabel("Tick: %d" % tick)
            tick_duration = int(tick * self.Ticktime)
            not_null = False
            duration = ""
            for value, format in [(tick_duration / DAY, "%dd"),
                                  ((tick_duration % DAY) / HOUR, "%dh"),
                                  ((tick_duration % HOUR) / MINUTE, "%dm"),
                                  ((tick_duration % MINUTE) / SECOND, "%ds")]:
                
                if value > 0 or not_null:
                    duration += format % value
                    not_null = True
            
            duration += "%gms" % (float(tick_duration % SECOND) / MILLISECOND) 
            self.TickTimeLabel.SetLabel("t: %s" % duration)
        else:
            self.TickLabel.SetLabel("")
            self.TickTimeLabel.SetLabel("")
        self.TickSizer.Layout()
    
    def UnregisterObsoleteData(self):
        self.SubscribeAllDataConsumers()
        
        if self.DataProducer is not None:
            if self.DataProducer is not None:
                self.SetTickTime(self.DataProducer.GetTicktime())
        
        for panel in self.GraphicPanels:
            panel.UnregisterObsoleteData()
            if panel.IsEmpty():
                if panel.HasCapture():
                    panel.ReleaseMouse()
                self.GraphicPanels.remove(panel)
                panel.Destroy()
        
        self.ResetVariableNameMask()
        self.RefreshGraphicsSizer()
        self.ForceRefresh()
    
    def ResetView(self):
        self.UnsubscribeAllDataConsumers()
        
        self.Fixed = False
        for panel in self.GraphicPanels:
            panel.Destroy()
        self.GraphicPanels = []
        self.ResetVariableNameMask()
        self.RefreshGraphicsSizer()
    
    def RefreshCanvasPosition(self):
        if len(self.Ticks) > 0:
            pos = int(self.StartTick - self.Ticks[0])
            range = int(self.Ticks[-1] - self.Ticks[0])
        else:
            pos = 0
            range = 0
        self.CanvasPosition.SetScrollbar(pos, self.CurrentRange, range, self.CurrentRange)
    
    def ChangeRange(self, dir, tick=None):
        current_range = self.CurrentRange
        current_range_idx = self.CanvasRange.GetSelection()
        new_range_idx = max(0, min(current_range_idx + dir, len(RANGE_VALUES) - 1))
        if new_range_idx != current_range_idx:
            self.CanvasRange.SetSelection(new_range_idx)
            self.CurrentRange = RANGE_VALUES[new_range_idx][1] / self.Ticktime
            if len(self.Ticks) > 0:
                if tick is None:
                    tick = self.StartTick + self.CurrentRange / 2.
                new_start_tick = tick - (tick - self.StartTick) * self.CurrentRange / current_range 
                self.StartTick = self.Ticks[numpy.argmin(numpy.abs(self.Ticks - new_start_tick))]
                self.Fixed = self.StartTick < self.Ticks[-1] - self.CurrentRange
            self.ForceRefresh()
    
    def RefreshRange(self):
        if len(self.Ticks) > 0:
            if self.Fixed and self.Ticks[-1] - self.Ticks[0] < self.CurrentRange:
                self.Fixed = False
            if self.Fixed:
                self.StartTick = min(self.StartTick, self.Ticks[-1] - self.CurrentRange)
            else:
                self.StartTick = max(self.Ticks[0], self.Ticks[-1] - self.CurrentRange)
        self.ForceRefresh()
    
    def OnRangeChanged(self, event):
        try:
            self.CurrentRange = RANGE_VALUES[self.CanvasRange.GetSelection()][1] / self.Ticktime
        except ValueError, e:
            self.CanvasRange.SetValue(str(self.CurrentRange))
        wx.CallAfter(self.RefreshRange)
        event.Skip()
    
    def OnCurrentButton(self, event):
        if len(self.Ticks) > 0:
            self.StartTick = max(self.Ticks[0], self.Ticks[-1] - self.CurrentRange)
            self.Fixed = False
            self.ResetCursorTick()
        event.Skip()
    
    def CopyDataToClipboard(self, variables):
        text = "tick;%s;\n" % ";".join([item.GetVariable() for item, data in variables])
        next_tick = NextTick(variables)
        while next_tick is not None:
            values = []
            for item, data in variables:
                if len(data) > 0:
                    if next_tick == data[0][0]:
                        var_type = item.GetVariableType()
                        if var_type in ["STRING", "WSTRING"]:
                            value = item.GetRawValue(int(data.pop(0)[2]))
                            if var_type == "STRING":
                                values.append("'%s'" % value)
                            else:
                                values.append('"%s"' % value)
                        else:
                            values.append("%.3f" % data.pop(0)[1])
                    else:
                        values.append("")
                else:
                    values.append("")
            text += "%d;%s;\n" % (next_tick, ";".join(values))
            next_tick = NextTick(variables)
        self.ParentWindow.SetCopyBuffer(text)
    
    def OnExportGraphButton(self, event):
        items = reduce(lambda x, y: x + y,
                       [panel.GetItems() for panel in self.GraphicPanels],
                       [])
        variables = [(item, [entry for entry in item.GetData()])
                     for item in items
                     if item.IsNumVariable()]
        wx.CallAfter(self.CopyDataToClipboard, variables)
        event.Skip()
    
    def OnPositionChanging(self, event):
        if len(self.Ticks) > 0:
            self.StartTick = self.Ticks[0] + event.GetPosition()
            self.Fixed = True
            self.ForceRefresh()
        event.Skip()
    
    def GetRange(self):
        return self.StartTick, self.StartTick + self.CurrentRange
    
    def GetViewerIndex(self, viewer):
        if viewer in self.GraphicPanels:
            return self.GraphicPanels.index(viewer)
        return None
    
    def IsViewerFirst(self, viewer):
        return viewer == self.GraphicPanels[0]
    
    def IsViewerLast(self, viewer):
        return viewer == self.GraphicPanels[-1]
    
    def HighlightPreviousViewer(self, viewer):
        if self.IsViewerFirst(viewer):
            return
        idx = self.GetViewerIndex(viewer)
        if idx is None:
            return
        self.GraphicPanels[idx-1].SetHighlight(HIGHLIGHT_AFTER)
    
    def ResetVariableNameMask(self):
        items = []
        for panel in self.GraphicPanels:
            items.extend(panel.GetItems())
        if len(items) > 1:
            self.VariableNameMask = reduce(compute_mask,
                [item.GetVariable().split('.') for item in items])
        elif len(items) > 0:
            self.VariableNameMask = items[0].GetVariable().split('.')[:-1] + ['*']
        else:
            self.VariableNameMask = []
        self.MaskLabel.ChangeValue(".".join(self.VariableNameMask))
        self.MaskLabel.SetInsertionPoint(self.MaskLabel.GetLastPosition())
            
    def GetVariableNameMask(self):
        return self.VariableNameMask
    
    def InsertValue(self, iec_path, idx = None, force=False):
        for panel in self.GraphicPanels:
            if panel.GetItem(iec_path) is not None:
                return
        if idx is None:
            idx = len(self.GraphicPanels)
        item = DebugVariableItem(self, iec_path, True)
        result = self.AddDataConsumer(iec_path.upper(), item)
        if result is not None or force:
            
            if item.IsNumVariable():
                panel = DebugVariableGraphic(self.GraphicsWindow, self, [item], GRAPH_PARALLEL)
                if self.CursorTick is not None:
                    panel.SetCursorTick(self.CursorTick)
            else:
                panel = DebugVariableText(self.GraphicsWindow, self, [item])
            if idx is not None:
                self.GraphicPanels.insert(idx, panel)
            else:
                self.GraphicPanels.append(panel)
            self.ResetVariableNameMask()
            self.RefreshGraphicsSizer()
            self.ForceRefresh()
    
    def MoveValue(self, iec_path, idx = None):
        if idx is None:
            idx = len(self.GraphicPanels)
        source_panel = None
        item = None
        for panel in self.GraphicPanels:
            item = panel.GetItem(iec_path)
            if item is not None:
                source_panel = panel
                break
        if source_panel is not None:
            source_panel.RemoveItem(item)
            source_size = source_panel.GetSize()
            if source_panel.IsEmpty():
                if source_panel.HasCapture():
                    source_panel.ReleaseMouse()
                self.GraphicPanels.remove(source_panel)
                source_panel.Destroy()
            
            if item.IsNumVariable():
                panel = DebugVariableGraphic(self.GraphicsWindow, self, [item], GRAPH_PARALLEL)
                panel.SetCanvasSize(source_size.width, source_size.height)
                if self.CursorTick is not None:
                    panel.SetCursorTick(self.CursorTick)
            else:
                panel = DebugVariableText(self.GraphicsWindow, self, [item])
            self.GraphicPanels.insert(idx, panel)
            self.ResetVariableNameMask()
            self.RefreshGraphicsSizer()
            self.ForceRefresh()
    
    def MergeGraphs(self, source, target_idx, merge_type, force=False):
        source_item = None
        source_panel = None
        for panel in self.GraphicPanels:
            source_item = panel.GetItem(source)
            if source_item is not None:
                source_panel = panel
                break
        if source_item is None:
            item = DebugVariableItem(self, source, True)
            if item.IsNumVariable():
                result = self.AddDataConsumer(source.upper(), item)
                if result is not None or force:
                    source_item = item
        if source_item is not None and source_item.IsNumVariable():
            if source_panel is not None:
                source_size = source_panel.GetSize()
            else:
                source_size = None
            target_panel = self.GraphicPanels[target_idx]
            graph_type = target_panel.GraphType
            if target_panel != source_panel:
                if (merge_type == GRAPH_PARALLEL and graph_type != merge_type or
                    merge_type == GRAPH_ORTHOGONAL and 
                    (graph_type == GRAPH_PARALLEL and len(target_panel.Items) > 1 or
                     graph_type == GRAPH_ORTHOGONAL and len(target_panel.Items) >= 3)):
                    return
                
                if source_panel is not None:
                    source_panel.RemoveItem(source_item)
                    if source_panel.IsEmpty():
                        if source_panel.HasCapture():
                            source_panel.ReleaseMouse()
                        self.GraphicPanels.remove(source_panel)
                        source_panel.Destroy()
            elif (merge_type != graph_type and len(target_panel.Items) == 2):
                target_panel.RemoveItem(source_item)
            else:
                target_panel = None
                
            if target_panel is not None:
                target_panel.AddItem(source_item)
                target_panel.GraphType = merge_type
                size = target_panel.GetSize()
                if merge_type == GRAPH_ORTHOGONAL:
                    target_panel.SetCanvasSize(size.width, size.width)
                elif source_size is not None:
                    target_panel.SetCanvasSize(size.width, size.height + source_size.height)
                else:
                    target_panel.SetCanvasSize(size.width, size.height)
                target_panel.ResetGraphics()
                
                self.ResetVariableNameMask()
                self.RefreshGraphicsSizer()
                self.ForceRefresh()
    
    def DeleteValue(self, source_panel, item=None):
        source_idx = self.GetViewerIndex(source_panel)
        if source_idx is not None:
            
            if item is None:
                source_panel.Clear()
                source_panel.Destroy()
                self.GraphicPanels.remove(source_panel)
                self.ResetVariableNameMask()
                self.RefreshGraphicsSizer()
            else:
                source_panel.RemoveItem(item)
                if source_panel.IsEmpty():
                    source_panel.Destroy()
                    self.GraphicPanels.remove(source_panel)
                    self.ResetVariableNameMask()
                    self.RefreshGraphicsSizer()
            self.ForceRefresh()
    
    def ResetGraphicsValues(self):
        self.Ticks = numpy.array([])
        self.StartTick = 0
        self.Fixed = False
        for panel in self.GraphicPanels:
            panel.ResetData()
        self.ResetCursorTick()

    def RefreshGraphicsWindowScrollbars(self):
        xstart, ystart = self.GraphicsWindow.GetViewStart()
        window_size = self.GraphicsWindow.GetClientSize()
        vwidth, vheight = self.GraphicsSizer.GetMinSize()
        posx = max(0, min(xstart, (vwidth - window_size[0]) / SCROLLBAR_UNIT))
        posy = max(0, min(ystart, (vheight - window_size[1]) / SCROLLBAR_UNIT))
        self.GraphicsWindow.Scroll(posx, posy)
        self.GraphicsWindow.SetScrollbars(SCROLLBAR_UNIT, SCROLLBAR_UNIT, 
                vwidth / SCROLLBAR_UNIT, vheight / SCROLLBAR_UNIT, posx, posy)
    
    def OnGraphicsWindowEraseBackground(self, event):
        pass
    
    def OnGraphicsWindowPaint(self, event):
        self.RefreshView()
        event.Skip()
    
    def OnGraphicsWindowResize(self, event):
        size = self.GetSize()
        for panel in self.GraphicPanels:
            panel_size = panel.GetSize()
            if (isinstance(panel, DebugVariableGraphic) and 
                panel.GraphType == GRAPH_ORTHOGONAL and 
                panel_size.width == panel_size.height):
                panel.SetCanvasSize(size.width, size.width)
        self.RefreshGraphicsWindowScrollbars()
        self.GraphicsSizer.Layout()
        event.Skip()

    def OnGraphicsWindowMouseWheel(self, event):
        if self.VetoScrollEvent:
            self.VetoScrollEvent = False
        else:
            event.Skip()