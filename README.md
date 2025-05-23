# Meteorological-ConversionTool-for-ArcGIS-Pro
# 概要
「気象データ変換ツール for ArcGIS Pro」 は、気象庁が保有し気象業務支援センターが提供する気象データを読み込み、ラスター(TIFF形式) へ変換を行う ArcGIS Pro 用のジオプロセシング ツールで、ArcGIS Pro を利用するライセンスをお持ちの方がご利用可能です。
ArcGIS Desktop をご利用の場合は、各バージョンに対応した「気象データ変換ツール」をご利用ください。  
[参考] ArcGISブログ： [気象データ変換ツール 10.8 対応版をリリース](https://blog.esrij.com/2020/07/29/post-36919/)


### 更新履歴
* 2024/02/20 ： 「気象データ変換ツール for ArcGIS Pro」 を公開
* 2024/03/03 ： ジオプロセシング ツール（`MetConv_toolbox.pyt`）とZIPファイルの更新
* 2024/03/08 : 「気象データ変換ツール for ArcGIS Pro」 をバージョン 1.1.0 に更新
  - 出力する TIFF を `圧縮なし`から `LZW圧縮` に変更
  - 解析雨量(RAP)のインポート でピクセル座標のずれが生じている件に対応
  - 利用ガイドの更新
* 2024/03/28 : 「気象データ変換ツール for ArcGIS Pro」 をバージョン 1.1.1 に更新
  - 日本語パスや半角スペースを含むディレクトリへツールを配置した際、変換に失敗する件に対応
* 2025/05/23 : 変換した気象データ（ラスターデータ）をメッシュ ポリゴンに変換するジオプロセシング ツール（`RasterConv_toolbox.pyt`）を追加

## ジオプロセシング ツールボックスの構成

「気象データ変換ツール for ArcGIS Pro」は、ArcGIS Desktop の気象データ変換ツールから一部機能を移植したコンソールアプリケーション（`met_cnv.exe`）と、そのコンソールアプリケーションをジオプロセシング ツールとして呼び出しするための[Python toolbox](https://pro.arcgis.com/ja/pro-app/latest/arcpy/geoprocessing_and_python/a-quick-tour-of-python-toolboxes.htm) （`MetConv_toolbox.pyt`） から構成されています。  
また、ツールボックス内には、変換対象の気象データに応じた次の９種類のジオプロセシング ツールで構成されています。

|ジオプロセシング ツール|`MetConv_toolbox.pyt`|
|:---|:---|
|解析雨量(RAP)のインポート|Import JMA Analysis Rap|
|解析雨量/速報版解析雨量のインポート|Import JMA Analysis|
|降水ナウキャストのインポート|Import JMA Nowcast|
|降水短時間予報/速報版短時間予報/降水15時間予報のインポート|Import JMA Forecast|
|高解像度降水ナウキャストのインポート|Impotr JMA High Resolution Nowcast |
|全国合成レーダーのインポート|Import JMA Radar|
|土砂災害警戒判定メッシュのインポート|Import JMA Dosha Mesh Analysis|
|土壌雨量指数/高頻度化土壌雨量指数のインポート|Import JMA Soil water index Analysis|
|土壌雨量指数予測値/高頻度化土壌雨量指数予測値のインポート|Import JMA Soil water index Forecast|
  
「気象データ変換ツール」で対応していたメッシュ ポリゴンへの変換 の代替として、変換した気象データ（ラスターデータ）をメッシュ ポリゴンに変換するジオプロセシング ツールを含む、[Python toolbox](https://pro.arcgis.com/ja/pro-app/latest/arcpy/geoprocessing_and_python/a-quick-tour-of-python-toolboxes.htm) （`RasterConv_toolbox.pyt`） を2025年5月に追加しました。  
ただし、汎用的なラスターをメッシュポリゴンに変換するツールのため、出力される属性は[ラスター → ポイント (Raster to Point) ](https://pro.arcgis.com/ja/pro-app/latest/tool-reference/conversion/raster-to-point.htm) と同様、入力ラスターのセル値 (VALUE フィールド) のみです。  
  
|ジオプロセシング ツール|`RasterConv_toolbox.pyt`|
|:---|:---|
|ラスターからメッシュポリゴンへ変換|ー|
  
  
  
### 動作環境
本ツールの動作環境は、以下の通りです。
- OS：
  [ArcGIS Pro 3.1 のサポートされているオペレーションシステム](https://pro.arcgis.com/ja/pro-app/3.1/get-started/arcgis-pro-system-requirements.htm) に準じる
- ArcGIS：
  ArcGIS Pro 3.1 以上（3.1.3 で動作確認）
- Microsoft .NET：
  - コンソールアプリケーションの要件：.NET Framework 4.8（Windows 11, Windows 10 May 2019 Update以降には含まれています）
  - ArcGIS Pro 3.1 のソフトウェア要件：Windows x64 インストーラーを使用した、Microsoft .NET Desktop Runtime [6.0.5](https://dotnet.microsoft.com/en-us/download/dotnet/thank-you/runtime-desktop-6.0.5-windows-x64-installer) または[それ以降のパッチ リリース](https://dotnet.microsoft.com/en-us/download/dotnet/6.0) (6.0.6 など) が必要
  
  ※ ArcGIS Pro 2.x や ArcGIS Pro 3.0 等でも問題なく動作するとは思いますが、ArcGIS Pro 3.1.3 の環境で動作確認を行っているため、上記環境でのご利用を推奨いたします。
  

### 利用方法
「[気象データ変換ツール for ArcGIS Pro](https://github.com/EsriJapan/Meteorological-ConversionTool-for-ArcGIS-Pro/releases/download/v1.2.0/MeteorologicalConversionTool_forPro.zip)」をダウンロードし、任意の場所にZIPファイルを解凍した上でご利用ください。  
インストール・アンインストール、操作方法や仕様に関する詳細は、一緒に配布している [気象データ変換ツール for ArcGIS Pro 利用ガイド](https://github.com/EsriJapan/Meteorological-ConversionTool-for-ArcGIS-Pro/blob/main/Doc/%E6%B0%97%E8%B1%A1%E3%83%87%E3%83%BC%E3%82%BF%E5%A4%89%E6%8F%9B%E3%83%84%E3%83%BC%E3%83%AB_forArcGISPro_%E5%88%A9%E7%94%A8%E3%82%AC%E3%82%A4%E3%83%89.pdf) をご参照の上、ご利用ください。
  

### 免責事項
* [MeteorologicalConversinTool] フォルダーに含まれる「気象データ変換ツール for ArcGIS Pro（ コンソールアプリケーション: `met_cnv.exe` と Python toolbox: `MetConv_toolbox.pyt`, `RasterConv_toolbox.pyt` ）」は、サンプルとして提供しているものであり、動作に関する保証、および製品ライフサイクルに従った Esri 製品サポート サービスは提供しておりません。
* 同様に [Meteorological_sample_script] フォルダーに含まれるフィールド演算式、Python ノートブック もサンプルとして提供しているものであり、動作に関する保証、および製品ライフサイクルに従った Esri 製品サポート サービスは提供しておりません。
* 上記記載の本ツール、フィールド演算式、Python ノートブック によって生じた損失及び損害等について、一切の責任を負いかねますのでご了承ください。
* 弊社で提供している[Esri 製品サポートサービス](https://www.esrij.com/services/maintenance/) では、本ツール、フィールド演算式、Python ノートブック に関しての Ｑ＆Ａ サポートの受付を行っておりませんので、予めご了承の上、ご利用ください。詳細は[
ESRIジャパン GitHub アカウントにおけるオープンソースへの貢献について](https://github.com/EsriJapan/contributing)をご参照ください。

## ライセンス
Copyright 2024 Esri Japan Corporation.

Apache License Version 2.0（「本ライセンス」）に基づいてライセンスされます。あなたがこのファイルを使用するためには、本ライセンスに従わなければなりません。
本ライセンスのコピーは下記の場所から入手できます。

> http://www.apache.org/licenses/LICENSE-2.0

適用される法律または書面での同意によって命じられない限り、本ライセンスに基づいて頒布されるソフトウェアは、明示黙示を問わず、いかなる保証も条件もなしに「現状のまま」頒布されます。本ライセンスでの権利と制限を規定した文言については、本ライセンスを参照してください。

ライセンスのコピーは本リポジトリの[ライセンス ファイル](./LICENSE)で利用可能です。
