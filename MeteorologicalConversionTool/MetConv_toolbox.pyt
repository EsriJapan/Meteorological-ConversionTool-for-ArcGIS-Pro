# coding: utf-8
"""
Name        : 「気象データ変換ツール for ArcGIS Pro」  MetConv_toolbox.pyt
Purpose     : ArcGIS Desktop のサポート終了が迫ってきたため、「気象データ変換ツール ArcGIS 10.8.x 対応版」 から
              GDAL を使ったスタンドアロンのEXE に変換ツールを移植。さらに同様のユーザーインターフェースとするために、
              ジオプロツールとして動作可能なように、EXE の呼出し部分をPython Toolbox として実装した。
              参考: Python Toolbox からEXE の呼出しは「WhiteboxTools-ArcGIS」のコードを参考にした
                    https://github.com/opengeos/WhiteboxTools-ArcGIS
            
              各ジオプロセシング ツールのツール名は「気象データ変換ツール ArcGIS 10.8.x 対応版」の
              ジオプロセシングツールでのツール名に揃えるが、EXE へ移植しているものと未移植のものがある。
              また、出力はTIFFのみに対応（制限事項）。詳細は次のとおり。
              a)GSM / MSM Analysit は未移植
                  Import JMA Japan region GSM Analysis  GSM(日本域)客観解析のインポート
                  Import JMA MSM Analysis               メソ客観解析のインポート
              b)EXE へ移植済み
                  Import JMA Radar                      全国合成レーダーのインポート
                  Import JMA Soil water Index Analysis  土壌雨量指数/高頻度化土壌雨量指数のインポート
                  Import JMA Soil water Index Forecast  土壌雨量指数予測値/高頻度化土壌雨量指数予測値のインポート
                  Import JMA Dosha Mesh Analysis        土砂災害警戒判定メッシュのインポート
                  Import JMA Analysis Rap               解析雨量(RAP)のインポート
                  Import JMA Analysis                   解析雨量/速報版解析雨量のインポート
                  Import JMA Nowcast                    降水ナウキャストのインポート
                  Import JMA Forcast                    降水短時間予報/速報版短時間予報/降水15時間予報のインポート
              c)EXE へ今回新規追加
                  Import JMA High Resolution Nowcast    高解像度降水ナウキャストのインポート
Author      :
Copyright   :
Created     :2023/12/12
Last Updated:2024/03/03
ArcGIS Version: ArcGIS Pro 3.1 以上 （ArcGIS Pro 3.1.3 で動作確認）
"""
import arcpy
import os
import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
import gzip
import shutil

# 
# 気象データ変換ツール( met_cnv.exe ) の呼出しを補助するクラス
# 
class MetConvUtil():
    """
    気象データ変換ツール( met_cnv.exe ) の呼出しを補助するクラス
    """
    # met_cnv.exe で対応している気象データ
    RADAR = "RADAR"         #全国合成レーダー
    SWI_ANAL = "SWI_ANAL"   #土壌雨量指数解析
    SWI_FCAST = "SWI_FCAST" #土壌雨量指数予測
    DOSHA = "DOSHA"         #土砂災害警戒判定メッシュ
    ANAL_RAP = "ANAL_RAP"   #解析雨量(RAP)
    ANAL = "ANAL"           #解析雨量
    NCAST = "NCAST"         #降水ナウキャスト
    FCAST = "FCAST"         #降水短時間予報/降水15時間予報
    NCAST_HR = "NCAST_HR"   #高解像度降水ナウキャスト
    
    # 気象データの種類のチェック用の正規表現
    # 気象データ変換ツール for ArcGIS では gp_met > ImportJmaBase.cs で定義されているもの
    S_RADAR = r"Z__C_RJTD_\d{14}_RDR_JMAGPV_Ggis1km_Prr\d{2}lv_ANAL_.*.bin"                               #全国合成レーダー
    S_SWI_ANAL = r"Z__C_RJTD_\d{14}_SRF_GPV_(Ggis1|Gll5)km_(P-swi|Psw)_(Aper10min_)?ANAL_.*.bin"          #土壌雨量指数/高頻度化土壌雨量指数
    S_SWI_FCAST = r"Z__C_RJTD_\d{14}_SRF_GPV_(Ggis1|Gll5)km_(P-swi|Psw)_(Fper10min_)?FH01-06_.*.bin"      #土壌雨量指数予測値/高頻度化土壌雨量指数予測値
    S_DOSHA = r"Z__C_RJTD_\d{14}_MET_INF_Jdosha_Ggis5km_ANAL_.*.bin"                                      #土砂災害警戒判定メッシュ
    S_ANAL_RAP = r".\d{4}.\d{2}\.RAP"                                                                     #解析雨量RAP
    S_ANAL = r"Z__C_RJTD_\d{14}_SRF_GPV_Ggis1km_Prr\d{2}lv_(Aper10min_)?ANAL_.*.bin"                      #解析雨量/速報版解析雨量
    S_NOWCAST = r"Z__C_RJTD_\d{14}_NOWC_GPV_Ggis1km_Prr(10|05)lv_FH00(10|05)-0100_.*.bin"                 #降水ナウキャスト
    S_FCAST = r"Z__C_RJTD_\d{14}_SRF_GPV_(Ggis1|Gll5)km_Prr60lv_(Fper10min_)?FH(01-06|07-15)_.*.bin"      #降水短時間予報/速報版短時間予報/降水15時間予報
    #S_NCAST_HR = r"Z__C_RJTD_\d{14}_NOWC_GPV_Ggis0p25km_Pr(i60|r05)lv_Aper5min_FH0000-0030_.*.bin"        #高解像度降水ナウキャスト(解凍後)
    S_NCAST_HR = r"Z__C_RJTD_\d{14}_NOWC_GPV_Ggis0p25km_Pr(i60|r05)lv_Aper5min_FH0000-0030_.*.bin.gz"     #高解像度降水ナウキャスト(gzip)
    
    def __init__(self, datatype):
        folder = os.path.dirname(__file__) #pyt が格納されているフォルダー
        met_folder = os.path.join(folder, "MET") # MET フォルダのディレクトリ
        self.exe_path = os.path.join(met_folder, "met_cnv.exe")
        self.datatype = datatype
        self.datatypes = {
            self.RADAR, self.SWI_ANAL, self.SWI_FCAST,
            self.DOSHA, self.ANAL_RAP, self.ANAL, 
            self.NCAST, self.FCAST, self.NCAST_HR,
        }
        self.reg_pattern = {
            self.RADAR:[self.S_RADAR], self.SWI_ANAL:[self.S_SWI_ANAL], self.SWI_FCAST:[self.S_SWI_FCAST],
            self.DOSHA:[self.S_DOSHA], self.ANAL_RAP:[self.S_ANAL_RAP], self.ANAL:[self.S_ANAL], 
            self.NCAST:[self.S_NOWCAST], self.FCAST:[self.S_FCAST], self.NCAST_HR:[self.S_NCAST_HR],
        }
        return

    def __del__(self):
        return

    def __str__(self):
        return "{}".format(self.datatype)

    def is_exe_exist(self):
        """ \MET\met_cnv.exe が存在するか"""
        return os.path.isfile(self.exe_path)

    def is_support(self):
        """サポートフォーマットかどうか"""
        if self.datatype in self.datatypes:
            return True
        return False

    def get_reg_pattern(self):
        """ファイル名チェックの正規表現のパターンを取得"""
        if self.is_support():
            return self.reg_pattern.get(self.datatype)[0]
        return None

    def get_format_name(self):
        """対応データ名を文字列で取得"""
        return self.__str__()

    def __create_cmd(self, args):
        """ met_cnv.exe のコマンドを作成 """
        cmd = " ".join(args)
        return '"{}" {}'.format(self.exe_path, cmd) # 2024.03.03 - exe_path に空白スペースが入った時にも対応

    def __ncast_hr_decompress(self, gzfile):
        """高解像度ナウキャストのgzipを解凍"""
        folder, gzfile_name = os.path.split(gzfile)
        outfile_name = gzfile_name[:-3] #.gz を除く
        outfile = os.path.join(folder, outfile_name)
        with gzip.open(gzfile, 'rb') as file_in:
            with open(outfile, 'wb') as file_out:
                shutil.copyfileobj(file_in, file_out)
        return outfile

    def run_exe(self, input_file, input_type, output_type, output_ws, output_data, \
                check_cell=False, clip_env=None, callback=None):
        """
        met_cnv.exe の引数定義
        引数           必須   内容
                       デフォルト
        --input_file   true     入力ファイル
        --input_type   true     入力形式指定 - Constants.cs -> JmaDataType
                                ANAL:解析雨量
                                FCAST:降水短時間予報/降水15時間予報
                                RADAR:全国合成レーダー
                                SWI_ANAL:土壌雨量指数解析
                                SWI_FCAST:土壌雨量指数予測
                                DOSHA:土砂災害警戒判定メッシュ
                                ANAL_RAP:解析雨量(RAP)
                                NCAST:降水ナウキャスト
                                NCAST_HR：高解像度ナウキャスト
        --output_type  true     出力形式指定(TIFF)
                                TIFF:現在はTIFFのみ
        --output_ws    true     出力ワークスペース/フォルダ
        --output_data  false    出力フィーチャクラス名/ファイル名
        --check_cell   false    セルサイズを緯度経度同値に分割して出力(true/false)
        --check_date   false    NetCDF時間設定/CSV時間項目の日時を日本標準時にする(true/false)
                                 ↑ TIFF のみなので使えない
        --check_nozero false    ０値以下のメッシュ出力を除外(true/false)
                                 ↑ TIFF のみなので使えない
        --clip_env     null     出力対象地域（緯度経度）
                                ymin  xmin  ymax  xmax
        --log_dir      null     ログ出力先フォルダ（未指定:出力しない）
        """
        args = []
        #高解像度ナウキャストの場合はgzip圧縮を解凍
        if input_type == self.NCAST_HR:
            input_file = self.__ncast_hr_decompress(input_file)
        args.append("--input_file \"{}\"".format(input_file))
        args.append("--input_type \"{}\"".format(input_type))
        args.append("--output_type \"{}\"".format(output_type))
        args.append("--output_ws \"{}\"".format(output_ws))
        args.append("--output_data \"{}\"".format(output_data))
        args.append("--check_cell \"{}\"".format( str(check_cell).lower() ))
        if clip_env is not None:
            args.append("--clip_env \"{}\"".format(clip_env))
        
        cmd = self.__create_cmd(args)
        arcpy.AddMessage(u"----- met_cnv.exe -----")
        arcpy.AddMessage(cmd)
        arcpy.AddMessage(u"-----------------------")
        #return cmd #コマンドが正しいかどうかのデバッグ確認用
        
        # run met_conv.exe
        result = subprocess.run(cmd, check=True, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        arcpy.AddMessage(result.stdout)
        # 高解像度ナウキャストの場合は解凍したファイルを削除
        if input_type == self.NCAST_HR:
            os.remove(input_file)
        return result.returncode

# 
# ジオプロセシング ツールボックスの定義
# - テンプレートは次を参照のこと
#   https://pro.arcgis.com/ja/pro-app/latest/arcpy/geoprocessing_and_python/a-template-for-python-toolboxes.htm
#
class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "気象データ変換ツール for ArcGIS Pro"
        self.alias = "metpro"

        # List of tool classes associated with this toolbox
        self.tools = [MetcnvRadar_Tool, MetcnvSwiAnal_Tool, MetcnvSwiFcast_Tool, \
                      MetcnvDosha_Tool, MetcnvAnalRap_Tool, MetcnvAnal_Tool, \
                      MetcnvNcast_Tool,MetcnvFcast_Tool, MetcnvNcastHR_Tool ]
    @classmethod
    def getExtentValue(cls, extent):
        """
        GPExtent を使っての座標変換はOSMQuery のコードを参考にした
        https://github.com/riccardoklinger/OSMquery/blob/master/OSMQuery.pyt
        """
        if extent.spatialReference == arcpy.SpatialReference(4326): # GCS_WGS_1984
            # No reprojection necessary for EPSG:4326 coordinates
            bounding_box = [extent.YMin, extent.XMin, extent.YMax, extent.XMax]
        else:
            # The coordinates of the extent object need to be reprojected
            # to EPSG:4326 for query 
            lower_left_pt = arcpy.PointGeometry(arcpy.Point(extent.XMin, extent.YMin), \
                extent.spatialReference).projectAs(arcpy.SpatialReference(4326))
            upper_right_pt = arcpy.PointGeometry(arcpy.Point(extent.XMax, extent.YMax), \
                extent.spatialReference).projectAs(arcpy.SpatialReference(4326))
            bounding_box = [lower_left_pt.extent.YMin, lower_left_pt.extent.XMin, \
                upper_right_pt.extent.YMax, upper_right_pt.extent.XMax]
        return (bounding_box[1], bounding_box[0], bounding_box[3], bounding_box[2])

    @classmethod
    def getOutfile(cls, filepath, outtype="TIFF"):
        file_name = Path(filepath).stem
        extension = ""
        if outtype == "TIFF": #TIFF | メッシュ | NetCDF | CSV
            extension = "tif" #.tif |  | .nc | .csv
        return "{}.{}".format(file_name, extension)

# 
# 気象データ変換ツール ArcGIS Pro 対応版 - 各ジオプロセシング ツールの定義
# 
# 各ジオプロセシング ツールのツール名は「気象データ変換ツール ArcGIS 10.8.x 対応版」の
# ジオプロセシングツールでのツール名に揃えるが、EXE へ移植しているものと未移植のものがある。
# また、出力はTIFFのみに対応（制限事項）。詳細は次のとおり。
# a)GSM / MSM Analysit は未移植
#     Import JMA Japan region GSM Analysis  GSM(日本域)客観解析のインポート
#     Import JMA MSM Analysis               メソ客観解析のインポート
# b)EXE へ移植済み
#     Import JMA Radar                      全国合成レーダーのインポート
#     Import JMA Soil water Index Analysis  土壌雨量指数/高頻度化土壌雨量指数のインポート
#     Import JMA Soil water Index Forecast  土壌雨量指数予測値/高頻度化土壌雨量指数予測値のインポート
#     Import JMA Dosha Mesh Analysis        土砂災害警戒判定メッシュのインポート
#     Import JMA Analysis Rap               解析雨量(RAP)のインポート
#     Import JMA Analysis                   解析雨量/速報版解析雨量のインポート
#     Import JMA Nowcast                    降水ナウキャストのインポート
#     Import JMA Forcast                    降水短時間予報/速報版短時間予報/降水15時間予報のインポート
# c)EXE へ今回新規追加
#     Import JMA High Resolution Nowcast    高解像度降水ナウキャストのインポート
class MetcnvRadar_Tool(object):
    """RADAR #全国合成レーダー"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "全国合成レーダーのインポート(Import JMA Radar)"
        self.description = "全国合成レーダー(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.RADAR) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：全国合成レーダーデータ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映        return
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"全国合成レーダーのデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvSwiAnal_Tool(object):
    """SWI_ANAL #土壌雨量指数解析"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "土壌雨量指数/高頻度化土壌雨量指数のインポート(Import JMA Soil water Index Analysis)"
        self.description = "土壌雨量指数/高頻度化土壌雨量指数(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.SWI_ANAL) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒(高頻度土壌雨量指数)／45×45秒(土壌雨量指数)で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：土壌雨量指数/高頻度化土壌雨量指数データ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒(高頻度土壌雨量指数)／45×45秒(土壌雨量指数)で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"土壌雨量指数/高頻度化土壌雨量指数のデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        #input_file = parameters[0].valueAsText
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        #output_data = parameters[3].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvSwiFcast_Tool(object):
    """SWI_FCAST #土壌雨量指数予測"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "土壌雨量指数予測値/高頻度化土壌雨量指数予測値のインポート(Import JMA Soil water Index Forecast)"
        self.description = "土壌雨量指数予測値/高頻度化土壌雨量指数予測値(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.SWI_FCAST) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒(高頻度土壌雨量指数予測)／45×45秒(土壌雨量指数予測)で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：土壌雨量指数予測値/高頻度化土壌雨量指数予測値データ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒(高頻度土壌雨量指数予測)／45×45秒(土壌雨量指数予測)で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"土壌雨量指数予測値/高頻度化土壌雨量指数予測値のデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        #input_file = parameters[0].valueAsText
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvDosha_Tool(object):
    """DOSHA 土砂災害警戒判定メッシュ"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "土砂災害警戒判定メッシュのインポート(Import JMA Dosha Mesh Analysis)"
        self.description = "土砂災害警戒判定メッシュ(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.DOSHA) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ45×45秒で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param6 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：土砂災害警戒判定メッシュデータ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ45×45秒で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"土砂災害警戒判定メッシュのデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvAnalRap_Tool(object):
    """ANAL_RAP" #解析雨量(RAP)"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "解析雨量(RAP)のインポート(Import JMA Analysis Rap)"
        self.description = "解析雨量(RAP)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.ANAL_RAP) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ45×45秒(5kmメッシュの場合)／22.5×22.5秒(2.5kmメッシュの場合)で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：解析雨量(RAP)データ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["RAP"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ45×45秒(5kmメッシュの場合)／22.5×22.5秒(2.5kmメッシュの場合)で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"解析雨量(RAP)のデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvAnal_Tool(object):
    """ANAL #解析雨量"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "解析雨量/速報版解析雨量のインポート(Import JMA Analysis)"
        self.description = "解析雨量/速報版解析雨量(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.ANAL) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：解析雨量/速報版解析雨量データ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"解析雨量/速報版解析雨量のデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvNcast_Tool(object):
    """NCAST #降水ナウキャスト"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "降水ナウキャストのインポート（Import JMA Nowcast）"
        self.description = "降水ナウキャスト(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.NCAST) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：降水ナウキャストデータ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #ファイル名を正規表現でチェック
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"降水ナウキャストのデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvFcast_Tool(object):
    """FCAST #降水短時間予報/降水15時間予報"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "降水短時間予報/速報版短時間予報/降水15時間予報のインポート(Import JMA Forcast)"
        self.description = "降水短時間予報/速報版短時間予報/降水15時間予報(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.FCAST) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #param4 セルサイズ15×15秒(降水短時間予報)／45×45秒(降水15時間予報)で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：降水短時間予報/速報版短時間予報/降水15時間予報データ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["bin"]
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ15×15秒(降水短時間予報)／45×45秒(降水15時間予報)で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #ファイル名を正規表現でチェック
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name, "TIFF"))
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"降水短時間予報/速報版短時間予報/降水15時間予報のデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

class MetcnvNcastHR_Tool(object):
    """NCAST_HR #高解像度ナウキャスト"""
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "高解像度降水ナウキャストのインポート(Import JMA High Resolution Nowcast)"
        self.description = "高解像度降水ナウキャスト(GRIB2)ファイルを変換します"
        self.category = "Meteorological Convert Tools"
        self.metutil = MetConvUtil(MetConvUtil.NCAST_HR) #MetConvUtil の初期化

    def getParameterInfo(self):
        """Define parameter definitions"""
        #param0 入力
        #param1 出力形式(移植バージョンはtiffのみ)
        #param2 出力フォルダ/ワークスペース
        #param3 出力ファイル名/フィーチャクラス名(*予測時間が(分)付加されます)
        #0分から30分先までは250m分解能、35分先から60分さきまでは1kmの分解能
        #param4 セルサイズ3.75×3.75秒(30分先まで)／15×15秒(35分先から60分先まで)で出力（オプション）
        #(未定義) 出力ファイル名/フィーチャクラス名/NetCDF時間設定/CSV時間項目の日時を日本標準時間にする
        #(未定義) 0値以下のメッシュ出力を除外（オプション）
        #param5 出力対象地域（緯度経度） （オプション）
        param0 = arcpy.Parameter(
            displayName= "入力：高解像度降水ナウキャストデータ",
            name="input_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.filter.list = ["gz"] #gzipfile
        
        param1 = arcpy.Parameter(
            displayName="出力フォルダ/ワークスペース",
            name="output_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="出力形式",
            name="output_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ["TIFF"]
        param2.value = "TIFF"
        
        param3 = arcpy.Parameter(
            displayName="出力ファイル名",
            name="output_data",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
            
        param4 = arcpy.Parameter(
            displayName="セルサイズ3.75×3.75秒(30分先まで)／15×15秒(35分先から60分先まで)で出力（オプション）",
            name="chk_cell",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = "False"

        param5 = arcpy.Parameter(
            displayName="出力対象地域（緯度経度） （オプション）",
            name="clip_env",
            datatype="GPExtent",
            parameterType="Optional",
            direction="Input")
            
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #入力ファイル名を正規表現でチェックし、問題がない場合に出力ファイル名に '元ファイル名.tif' を表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            output_files_list = []
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    return
                #param1にフォルダー、param3にファイル名を設定
                if parameters[1].value is None:
                    parameters[1].value = "" #param1の値をクリア
                    parameters[1].value = os.path.dirname(input_file)
                if parameters[3].value is None:
                    output_files_list.append(Toolbox.getOutfile(file_name[:-3], "TIFF")) #.gz を除く
            #noneの時だけparam3に値を設定
            if parameters[3].value is None:
                parameters[3].value = "" #param3の値をクリア
                parameters[3].value = ";".join(output_files_list) # multiple 設定を出力ファイル名 のパラメータに反映
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #ファイル名を正規表現でチェック
        #multiValue=True にしているためエラーがあるパラメータ番号と一緒にエラーを表示
        if parameters[0].value is not None:
            input_files_list = parameters[0].valueAsText.split(';')
            check_results_list = []
            bl_check_result = False
            i = 0
            for input_file in input_files_list:
                file_name = os.path.basename(input_file)
                if re.fullmatch(self.metutil.get_reg_pattern(), file_name) == None:
                    check_results_list.append("パラメータ番号{}:{}".format(i,u"高解像度降水ナウキャストのデータではないようです") )
                    bl_check_result = True
                i = i + 1
            if bl_check_result:
                parameters[0].setErrorMessage(";".join(check_results_list))
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # EXEの配置チェック
        if self.metutil.is_exe_exist() == False:
            arcpy.AddError(u"\MET\met_cnv.exe が正しく配置されていません")
            return
        # パラメータを取得
        input_files_list = parameters[0].valueAsText.split(';')
        output_ws = parameters[1].valueAsText
        output_type = parameters[2].valueAsText
        output_data_list = parameters[3].valueAsText.split(';')
        chk_cell = parameters[4].valueAsText
        clip_env = None
        if parameters[5].value is not None:
            ext_min_x, ext_min_y, ext_max_x, ext_max_y = Toolbox.getExtentValue(parameters[5].value)
            clip_env = "{} {} {} {}".format(ext_min_y, ext_min_x, ext_max_y, ext_max_x)
        # met_cnv.exe を繰り返し実行
        for input_file, output_data in zip(input_files_list, output_data_list):
            arcpy.AddMessage(u"{} の変換開始".format(os.path.basename(input_file)) )
            returncode = self.metutil.run_exe(input_file, self.metutil.get_format_name(), output_type, output_ws, output_data, chk_cell, clip_env)
            if returncode == 0:
                arcpy.AddMessage(u"変換終了")
            else:
                arcpy.AddError(u"変換失敗")
            arcpy.AddMessage(u"\u200B") #改行
        return

