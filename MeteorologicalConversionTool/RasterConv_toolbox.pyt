# -*- coding: utf-8 -*-
# coding: utf-8
"""
Name        : RasterConv_toolbox.pyt
Purpose     : 「気象データ変換ツール for ArcGIS Pro」 等で変換したラスターをメッシュポリゴンに変換するツール
              ArcGIS Pro で浮動小数点のラスターを、メッシュポリゴンに変換するのは容易ではないため、
              ラスターの col, row の値からポリゴンの座標を計算して、ラスターのピクセル値とともに出力
Author      :
Copyright   :
Created     :2025/05/22
Last Updated:
ArcGIS Version: ArcGIS Pro 3.3 以上 （ArcGIS Pro 3.4.2 で動作確認）
"""

import arcpy
import numpy as np
import os
import pandas as pd
from shapely.geometry import box
import shapely
from typing import Tuple

# 
# 呼び出しを補助するクラス
# 
class Arcpy_XyColrowConverter:
    """
    arcpy でラスターの x,y と col,row の相互変換 
    """
    def __init__(self, raster_file: str):
        self.raster = arcpy.Raster(raster_file)
        self.xmin = self.raster.extent.XMin
        self.ymax = self.raster.extent.YMax
        self.cell_width = self.raster.meanCellWidth
        self.cell_height = -self.raster.meanCellHeight
        return
    def __del__(self):
        self.raster = None
        return
    #public
    def xy_to_colrow(self, x: float, y: float) -> Tuple[int, int]:
        col = (x - self.xmin) / self.cell_width
        row = (y - self.ymax) / self.cell_height
        return int(col), int(row)
    def colrow_to_xy(self, col: int, row: int) -> Tuple[float, float]:
        x = self.xmin + col * self.cell_width
        y = self.ymax + row * self.cell_height
        return x, y
    def colrow_to_centerxy(self, col: int, row: int) -> Tuple[float, float]:
        x, y = self.colrow_to_xy(col + 0.5, row + 0.5)
        return x, y
    def colrow_to_bound(self, col: int, row: int) -> Tuple[float, float, float, float]:
        xmin , ymax = self.colrow_to_xy(col, row)
        xmax , ymin = self.colrow_to_xy(col + 1, row + 1)
        return xmin, ymin, xmax, ymax

class Arcpy_RasterTileCreator:
    """
    arcpy.RasterToNumPyArray と Arcpy_XyColrowConverter を使って
    value, geometry(mesh polygon or mesh center point) をタプルにするクラス
    ※geometryはパフォーマンスを考慮してshapelyのジオメトリを使う
    """
    def __init__(self, raster_file):
        self.rasterfile = raster_file
        self.raster = arcpy.Raster(self.rasterfile)
        self.spref = self.raster.spatialReference
        self.nodata = self.raster.noDataValue
        self.array = arcpy.RasterToNumPyArray(self.raster)
        self.cell_width = self.raster.meanCellWidth
        self.cell_height = -self.raster.meanCellHeight
        return
    def __del__(self):
        self.array = None
        self.raster = None
        return
    #private
    def __createPolyArcpy(self, center_pt_x, center_pt_y, x_width, y_height, spref):
        """中心のポイントX,YをもとにExtentのポリゴンを作成（未使用）"""
        w_cx = x_width * 0.5
        h_cy = y_height * 0.5
        xmin = center_pt_x - w_cx;
        ymin = center_pt_y - h_cy;
        xmax = center_pt_x + w_cx;
        ymax = center_pt_y + h_cy;
        #四隅の座標を指定してポリゴンを作成
        pt1 = arcpy.Point(xmin, ymin)
        pt2 = arcpy.Point(xmin, ymax)
        pt3 = arcpy.Point(xmax, ymax)
        pt4 = arcpy.Point(xmax, ymin)
        array = arcpy.Array()
        array.add(pt1)
        array.add(pt2)
        array.add(pt3)
        array.add(pt4)
        array.add(pt1)
        polygon = arcpy.Polygon(array, spref) # 緯度経度の場合は、第二引数のspatial_reference を設定した方がよい
        return polygon
    def __createExtentPolyArcpy(self, xmin, ymin, xmax, ymax, spref):
        """四隅の座標を指定してポリゴンを作成（未使用）"""
        pt1 = arcpy.Point(xmin, ymin)
        pt2 = arcpy.Point(xmin, ymax)
        pt3 = arcpy.Point(xmax, ymax)
        pt4 = arcpy.Point(xmax, ymin)
        array = arcpy.Array()
        array.add(pt1)
        array.add(pt2)
        array.add(pt3)
        array.add(pt4)
        array.add(pt1)
        polygon = arcpy.Polygon(array, spref) # 緯度経度の場合は、第二引数のspatial_reference を設定した方がよい
        return polygon
    def __createPolyShapely(self, center_pt_x, center_pt_y, x_width, y_height):
        """中心のポイントX,YをもとにExtentのポリゴンを作成"""
        w_cx = x_width * 0.5
        h_cy = y_height * 0.5
        xmin = center_pt_x - w_cx;
        ymin = center_pt_y - h_cy;
        xmax = center_pt_x + w_cx;
        ymax = center_pt_y + h_cy;
        polygon = box(xmin, ymin, xmax, ymax)
        return polygon
    def __createPointShapely(self, center_pt_x, center_pt_y):
        """中心のポイントを作成"""
        return Point(center_pt_x, center_pt_y)
    #public
    def gen_tiles(self, show_msg=False):
        """value, geometry(polygon) のタプルを作成"""
        xycolrow_conv = Arcpy_XyColrowConverter(self.rasterfile)
        meshs = []
        (rows, columns) = self.array.shape #rows, columns
        num = np.count_nonzero(self.array > self.nodata) # nodata以外のセル数
        cnt = 0
        d = len(str(num))-1
        cnt_base = int(10**d * 0.5)
        for row in range(0, rows):
            for col in range(0, columns):
                #pixel value
                value = self.array[row, col]
                if value > self.nodata:
                    cnt = cnt + 1
                    if show_msg:
                        #if (cnt == 1) or (cnt == num) or (cnt % 10000 == 1):
                        #    s = u"    {0}/{1}の メッシュの座標を計算中・・・".format(cnt, num)
                        if (cnt == 1):
                            s = u"    {0}/{1}の メッシュの座標を計算開始・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                        elif (cnt == num):
                            s = u"    {0}/{1}の メッシュの座標を計算終了・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                        elif (cnt % cnt_base == 1):
                            s = u"    {0}/{1}の メッシュの座標を計算中・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                    x, y = xycolrow_conv.colrow_to_centerxy(col, row)
                    poly = self.__createPolyShapely(x, y, self.cell_width, self.cell_height)
                    m = [value, poly]
                    #メッシュの4隅の座標や、col,row なども保存する場合
                    #xmin, ymin, xmax, ymax = xycolrow_conv.colrow_to_bound(col, row)
                    #m = [col, row, xmin, ymin, xmax, ymax, value, poly]
                    meshs.append(m)
        del xycolrow_conv
        return tuple(meshs)
    def gen_tiles_pt(self, show_msg=False):
        """value, geometry(point) のタプルを作成"""
        xycolrow_conv = Arcpy_XyColrowConverter(self.rasterfile)
        mesh_pts = []
        (rows, columns) = self.array.shape #rows, columns
        num = np.count_nonzero(self.array > self.nodata) # nodata以外のセル数
        cnt = 0
        d = len(str(num))-1
        cnt_base = int(10**d * 0.5)
        for row in range(0, rows):
            for col in range(0, columns):        
                #pixel value
                value = self.array[row, col]
                if value > self.nodata:
                    cnt = cnt + 1
                    if show_msg:
                        #if (cnt == 1) or (cnt == num) or (cnt % 10000 == 1):
                        #    s = u"    {0}/{1}の メッシュの座標を計算中・・・".format(cnt, num)
                        if (cnt == 1):
                            s = u"    {0}/{1}の メッシュの座標を計算開始・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                        elif (cnt == num):
                            s = u"    {0}/{1}の メッシュの座標を計算終了・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                        elif (cnt % cnt_base == 1):
                            s = u"    {0}/{1}の メッシュの座標を計算中・・・".format(cnt, num)
                            arcpy.AddMessage(s)
                    x, y = xycolrow_conv.colrow_to_centerxy(col, row)
                    pt = self.__createPointShapely(x, y)
                    m = [value, pt]
                    mesh_pts.append(m)
        del xycolrow_conv
        return tuple(mesh_pts)

class Arcpy_RasterToFeatureConverter:
    """
    arcpy を使ってラスターをメッシュポリゴンとして変換するクラス
    ※ラスターのピクセル値は浮動小数点のまま出力
    """
    def __init__(self, infile):
        self.rasterfile = infile
        self.raster = arcpy.Raster(self.rasterfile)
        self.spref = self.raster.spatialReference
        return
    def __del__(self):
        self.raster = None
        arcpy.management.ClearWorkspaceCache() #clean up lock
        return
    #private
    def __createMeshFeatureClass(self, out_ws, out_poly, spref):
        arcpy.env.workspace = out_ws
        #shapefileの場合idフィールドが自動的に作成される
        out_fc = arcpy.CreateFeatureclass_management(out_ws, out_poly, "POLYGON", "", "DISABLED", "DISABLED", spref)        
        #メッシュの4隅の座標や、col,row なども保存する場合
        #arcpy.AddField_management(out_poly, "col", "LONG")
        #arcpy.AddField_management(out_poly, "row", "LONG")
        #arcpy.AddField_management(out_poly, "xmin", "DOUBLE")
        #arcpy.AddField_management(out_poly, "ymin", "DOUBLE")
        #arcpy.AddField_management(out_poly, "xmax", "DOUBLE")
        #arcpy.AddField_management(out_poly, "ymax", "DOUBLE")
        arcpy.AddField_management(out_poly, "value", "DOUBLE")
        return
    def __writeToFeatureClass(self, out_ws, out_poly, tiles, show_msg=False):
        arcpy.env.workspace = out_ws
        output = os.path.join(out_ws, out_poly)
        #fields = ['col','row','xmin','ymin','xmax','ymax','value','SHAPE@']
        fields = ['value','SHAPE@']
        cnt = 0
        num = len(tiles)
        d = len(str(num))-1
        cnt_base = int(10**d * 0.5)
        with arcpy.da.InsertCursor(output, fields) as cursor:
            for i in range(len(tiles)):
                cnt += 1
                if (show_msg):
                    #if (cnt == 1) or (cnt == num) or (cnt % 10000 == 1):
                    #    s = u"    {0}/{1}の インサート処理中・・・".format(cnt, num)
                    if (cnt == 1):
                        s = u"    {0}/{1}の インサート処理開始・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                    elif (cnt == num):
                        s = u"    {0}/{1}の インサート処理終了・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                    elif (cnt % cnt_base == 1):
                        s = u"    {0}/{1}の インサート処理中・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                #一旦取り出して、shapelyのポリゴンをarcpyのポリゴンに変換してインサート
                val, geom = tiles[i]
                cursor.insertRow( (val, arcpy.FromWKB(shapely.to_wkb(geom))) )
        del output
        return
    def __writeDataframeToFeatureClass(self, out_ws, out_poly, df, show_msg=False):
        arcpy.env.workspace = out_ws
        output = os.path.join(out_ws, out_poly)
        #fields = ['col','row','xmin','ymin','xmax','ymax','value','SHAPE@']
        fields = ['value','SHAPE@']
        cnt = 0
        num = df.shape[0]
        d = len(str(num))-1
        cnt_base = int(10**d * 0.5)
        with arcpy.da.InsertCursor(output, fields) as cursor:
            for row in df.itertuples():
                cnt += 1
                if (show_msg):
                    #if (cnt == 1) or (cnt == num) or (cnt % 10000 == 1):
                    #    s = u"    {0}/{1}の インサート処理中・・・".format(cnt, num)
                    if (cnt == 1):
                        s = u"    {0}/{1}の インサート処理開始・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                    elif (cnt == num):
                        s = u"    {0}/{1}の インサート処理終了・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                    elif (cnt % cnt_base == 1):
                        s = u"    {0}/{1}の インサート処理中・・・".format(cnt, num)
                        arcpy.AddMessage(s)
                #一旦取り出して、shapelyのポリゴンをarcpyのポリゴンに変換してインサート
                val, geom = row[1::]
                cursor.insertRow( (val, arcpy.FromWKB(shapely.to_wkb(geom))) )
        del output
        return               
    #public
    def convert_to_mesh_tiles(self, show_msg=False):
        """メッシュポリゴンをtupleにするメソッド"""
        rasTileCreator = Arcpy_RasterTileCreator(self.rasterfile)
        rasTiles = rasTileCreator.gen_tiles(show_msg)
        del rasTileCreator
        return rasTiles
    def convert_to_mesh_dataframe(self, show_msg=False):
        """メッシュポリゴンをpandas dataframeにするメソッド"""
        #convert raster to mesh tile polygon
        rasTiles = self.convert_to_mesh_tiles(show_msg)
        mpd = pd.DataFrame(rasTiles, columns=['value','shape'])
        del rasTiles
        return mpd
    def convert_to_mesh_file(self, outfile, usedf=False, show_msg=False):
        """メッシュポリゴンをフィーチャクラスにするメソッド"""
        out_ws = os.path.dirname(outfile)
        out_poly = os.path.basename(outfile)
        #create featureclass
        self.__createMeshFeatureClass(out_ws, out_poly, self.spref)
        if (usedf):
            #a)DataFrameを介して書き出す場合
            #convert raster to mesh tile polygon
            mpd = self.convert_to_mesh_dataframe(show_msg)
            #write mesh tile polygon to featureclass
            self.__writeDataframeToFeatureClass(out_ws, out_poly, mpd, show_msg)
        else:
            #b)tupleのまま書き出す場合
            tiles = self.convert_to_mesh_tiles(show_msg)
            self.__writeToFeatureClass(out_ws, out_poly, tiles, show_msg)
        del out_ws
        del out_poly
        return

# 
# ジオプロセシング ツールボックスの定義
# - テンプレートは次を参照のこと
#   https://pro.arcgis.com/ja/pro-app/latest/arcpy/geoprocessing_and_python/a-template-for-python-toolboxes.htm
#
class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "ラスターから独自変換ツール"
        self.alias = "rasconv"

        # List of tool classes associated with this toolbox
        self.tools = [RasToMeshpoly_Tool]

class RasToMeshpoly_Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "ラスターからメッシュポリゴンへ変換"
        self.description = "ラスターからメッシュポリゴンへ変換します(浮動小数点タイプのラスターも変換可能)"
        
    def getParameterInfo(self):
        """Define the tool parameters."""
        #param0 入力ラスター
        #param1 出力フォルダ/ワークスペース
        #param2 出力ファイル名/フィーチャクラス名
        param0 = arcpy.Parameter(
            displayName= "入力ラスター",
            name="input_raster",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input")
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
        
        param2 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        
        params = [param0, param1, param2]
        return params

    def isLicensed(self):
        """Set whether the tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[0].value is not None:
            #param2にファイル名を設定
            if parameters[2].value is None:
                parameters[2].value = ""
                parameters[2].value = os.path.basename(parameters[0].valueAsText).split('.')[0]
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        #パラメータを取得
        input_raster = parameters[0].valueAsText
        out_ws = parameters[1].valueAsText
        out_poly = parameters[2].valueAsText
        out_file = os.path.join(out_ws, out_poly)
        
        #変換クラスを使ってポリゴンに変換
        try:
            arcpy.AddMessage(u"{} のメッシュポリゴンへの変換開始".format(os.path.basename(input_raster)) )
            arcpy_conv = Arcpy_RasterToFeatureConverter(input_raster)
            arcpy_conv.convert_to_mesh_file(out_file, show_msg=True)
            arcpy.AddMessage(u"{} への変換終了".format(out_file) )
            arcpy.AddMessage(u"\u200B") #改行
        except Exception as e:
            arcpy.AddError(e.args[0])
            arcpy.AddMessage(u"\u200B") #改行
        finally:
            del arcpy_conv
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
