# hakoniwa-fpv-drone

> 組む前に飛ばす。

`hakoniwa-fpv-drone` は、FPVドローンの部品カタログと機体Recipeから、仮想BOM、物理特性、MuJoCoモデル、Hakoniwa Drone PRO設定を生成する機体構成・モデル生成ツールです。

Betaflightの再実装でも、操縦練習ゲームでもありません。部品を購入して組み立てる前に、候補構成を仮想的に組み、質量・重心・慣性・推力重量比などを確認し、簡易制御で試験する設計プロセスを作ることが目的です。

## Hakoniwa Drone PROとの関係

このリポジトリは設計入力と生成処理を管理し、[TOPPERS/hakoniwa-drone-core](https://github.com/toppers/hakoniwa-drone-core)を基盤とする箱庭ドローンPROを物理・制御ランタイムとして使用します。

- 本リポジトリ: Catalog、Recipe、物理モデルCompiler、生成Package
- Drone PRO: MuJoCo機体物理、Rotor/Battery、Mixer、Radio Controller、Rate/Angle PID、箱庭連携
- Three.js: optionalなブラウザ表示backend。既存機体GLB、プロペラ回転、搭載カメラとFPVコース表示を利用します

Drone PROは `drone_config.json` と `drone.xml` を使用します。コントローラの現在のランタイム形式はテキストパラメータなので、構造化された `control-param.json` と実行用 `control-param.txt` の両方を生成します。

## 4つの境界

```text
Component Catalog       利用可能な部品と、その根拠付き属性
       +
Vehicle Recipe          ユーザーが組みたい一台の構成
       ↓ resolve / compile
Resolved Vehicle Model  計算済みの質量、重心、慣性、Rotor配置など
       ↓ render
Generated Package       MuJoCo/Hakoniwaが利用する成果物
```

Catalog属性を追加してもRecipeの参照形式を壊さず、実行backend固有形式はGenerator内へ閉じ込める設計です。詳細は[アーキテクチャ](docs/architecture.md)を参照してください。

## Quick Start

このリポジトリは[箱庭ビジネスパック](https://github.com/hakoniwalab/hakoniwa-business-pack)の環境で使います。Python環境は、Business PackのFoundation Python（Python 3.12）に一本化します。

```bash
mkdir fpv-drone && cd fpv-drone
git clone https://github.com/hakoniwalab/hakoniwa-business-pack.git
git clone https://github.com/hakoniwalab/hakoniwa-fpv-drone.git
cd hakoniwa-business-pack
python3.12 tools/recipe.py doctor --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py configure --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

`configure`がFoundationのビルド、必要な兄弟リポジトリのclone、Python依存のインストールを行います。そのあと、drone-coreのバイナリを用意して機体を生成し、PS5で飛ばすまでの手順は、[Angleモードで実行する](#angleモードで実行するcloneからps5操縦まで)を参照してください。

機体の検証、BOM、生成パッケージだけを確認したい場合は、Business PackのWorkspace（`(hako)`プロンプト）の中で生成ツールを実行します。

```bash
cd hakoniwa-business-pack
python tools/workspace.py enter
cd ../hakoniwa-fpv-drone
export PYTHONPATH=src
python -m fpv_drone_generator.cli validate recipes/examples/5inch-fpv.yaml
python -m fpv_drone_generator.cli bom recipes/examples/5inch-fpv.yaml
python -m fpv_drone_generator.cli generate \
  recipes/examples/5inch-fpv.yaml \
  --world recipes/environments/fpv-training-course.yaml \
  --output build/example-5inch
```

Workspaceの中では、`python`はFoundation Pythonを指します。

## CatalogとRecipe

Catalogは部品そのものです。

実製品の写真・寸法から表示モデルを作る際は、[外観再現に必要な情報と受入要件](docs/catalog-visual-input-requirements.md)を参照してください。

```text
catalogs/
├── products/
│   └── <kind>/
│       ├── hakoniwa.yaml              # Hakoniwa generic category collection
│       └── <vendor>/<product>.yaml    # commercial product fragment
└── sources/<kind>/<vendor>/<product>.yaml
```

Recipeは部品IDを参照して、ユーザーが組みたい機体を定義します。

```yaml
schema_version: 1
name: example-5inch-fpv
type: quad_x
components:
  frame: generic_5inch_x
  motors: {product: generic_2207_1850kv, count: 4}
  propeller: generic_5inch_3blade
  battery: generic_6s_1300mah
  camera: generic_fpv_camera
controller:
  product: hakoniwa_default
  mode: angle
```

詳しくは[Catalog仕様](docs/catalog-spec.md)、[Recipe仕様](docs/recipe-spec.md)、
[Assembly Interface Specification](docs/assembly-interface-spec.md)を参照してください。

Assembly Interfaceは、Browser Composerが部品を接続してVehicle Recipeへ投影するための
契約です。部品固有のportはCatalogが所有し、port間の接続ruleは独立したinterface
variantで定義します。ComposerはこのAssembly Graphを編集するだけで、物理特性と
MuJoCo / Drone PRO成果物は既存のPython Generatorが生成します。

営業デモ向けの[Browser Composer](docs/browser-composer.md)は、このAssembly Graphを
Three.jsで編集する静的フロントエンドです。

## FPV飛行コース

機体Recipeとは独立した[FPV World YAML](docs/fpv-world.md)で、明るい空・照明・地面と、ゲート、パイロン、壁などの物理障害物を定義できます。既定コースは`recipes/environments/fpv-training-course.yaml`です。機体を変えても同じコースを再利用でき、コースだけを差し替えることもできます。

Drone PROで起動すると、機体の`fpv`カラを全面に、自由に操作できる客観カラをViewer左上のPiPに表示します。`Tab`キーで両者を入れ替え、`F`キーでPiPを表示・非表示できます。

## optional Three.js Viewer

通常のMuJoCo実行経路を変えず、`configure`へ`--threejs`を付けた場合だけ、Visual State Publisher、WebBridge、HTTP serverをLauncherへ追加できます。

Assembly Graphから、Three.js用の機体ボディ・プロペラ・カメラの3つのGLBと
viewer用の配置定義を生成する場合は、[Assembly Graph to Three.js assets](docs/threejs-assembly-assets.md)
を参照してください。`--assembly`を指定すると`configure --threejs`へも接続できます。

```bash
python3.12 tools/fpv.py configure --threejs
python3.12 tools/fpv.py start
python3.12 tools/fpv.py open-viewer
```

例えばMaster3XのCatalog外観を表示する場合は、次のようにAssembly Graphを指定します。

```bash
python3.12 tools/fpv.py configure --threejs \
  --assembly recipes/examples/master3x-visual-demo.assembly.json
```

`open-viewer`は生成済みURLを既定ブラウザで自動的に開きます。Three.jsではMuJoCo runtimeモデルの`fpv`カメラ位置・向き・FOVを正本として、主観映像をメイン、操作可能な客観映像を左上PiPに表示します。`Tab`で主・副画面を交換し、`F`でPiPを表示・非表示にできます。

ブラウザでは既存のThree.js機体GLBを使い、`DroneVisualStateArray`の位置・姿勢・PWMから機体移動と4枚のプロペラ回転を表示します。外観モデル全体は、生成機体のモーター対角距離（wheelbase）とThree.js基準機体のwheelbaseから求めた倍率でスケールされます。世界座標やコースにはこの倍率を適用しません。

FPVコースはGLBとして二重管理せず、World YAMLを正本として`fpv-course.json`へ生成します。Three.js側の`environment.type: fpv-course`は明示指定時だけ有効で、従来のGLB/MJCF環境には影響しません。`--threejs`なしの通常手順も従来どおりです。

## Hakoniwa Business Packから利用する

FPV固有のComponent CatalogとVehicle Recipeはこのリポジトリを正本とします。Business Pack側にはコンポーネントの検索Catalogだけを置き、システム構成Recipeもこのリポジトリの[FPV設計・Angle飛行Recipe](recipes/business-pack/fpv-drone-design-angle-flight.yaml)を参照します。これにより、FPVの設定や実行手順を二重管理しません。

兄弟ディレクトリに`hakoniwa-business-pack`がある場合、Business Packの共通入口からガイド、診断、構築計画を利用できます。cloneからPS5操縦までの一連の手順は、[Angleモードで実行する](#angleモードで実行するcloneからps5操縦まで)を参照してください。

```bash
cd ../hakoniwa-business-pack
python3.12 tools/recipe.py guide \
  --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py doctor \
  --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py plan \
  --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

Business Pack Recipeと`recipes/examples/5inch-fpv.yaml`は役割が異なります。前者はHakoniwaコンポーネント、Foundation、ライセンス境界、起動・停止を含むシステム構成で、後者はユーザーが組みたい一台のFPV機体構成です。

## Generated Package

```text
build/example-5inch/
├── recipe.yaml
├── world.yaml              # --world指定時
├── fpv-course.json         # --world指定時、optional Three.js表示入力
├── resolved-components.yaml
├── bom.yaml
├── drone.xml
├── drone_config.json
├── control-param.json
├── control-param.txt
└── report.json
```

`control-param.json` は値と由来を保持する設計用データ、`control-param.txt` は現行Drone PROが読むruntime adapterです。`report.json` は計算結果、未計算項目、近似、生成物hashを保持します。詳細は[Generated Package](docs/generated-package.md)を参照してください。

## テスト

```bash
PYTHONPATH=src python -m unittest discover -v
```

MuJoCo Python bindingがある環境では、生成XMLを `MjModel.from_xml_path()` でロードするテストも実行します。ない場合はその1件だけskipします。

## Angleモードで実行する（cloneからPS5操縦まで）

macOS（Apple Silicon）で、生成した機体をMuJoCo ViewerとPS5 DualSenseで操縦するまでの手順です。物理・制御ランタイムには無償版の[hakoniwa-drone-core](https://github.com/toppers/hakoniwa-drone-core) v4.1.1のリリースバイナリを使い、`hakoniwa-drone-pro`は不要です（PID自動チューニングだけはPROライセンスが必要です）。

前提：Python 3.12（Homebrew版は不可）、Xcode Command Line Tools、`brew install glfw`、PS5コントローラをBluetoothまたはUSBで接続済み。

### 1. 2つのリポジトリを同じ親ディレクトリへcloneする

```bash
mkdir fpv-drone && cd fpv-drone
git clone https://github.com/hakoniwalab/hakoniwa-business-pack.git
git clone https://github.com/hakoniwalab/hakoniwa-fpv-drone.git
```

以降のコマンドは、特に断りがなければ`hakoniwa-business-pack`で実行します。

### 2. Recipeを診断し、Foundationと依存を構築する

```bash
cd hakoniwa-business-pack
python3.12 tools/recipe.py doctor --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py configure --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

`configure`は、不足している兄弟リポジトリ（`hakoniwa-core-pro`、`hakoniwa-pdu-python`、`hakoniwa-drone-core` v4.1.1）をcloneし、Foundation（`work/foundation/install`）をビルドし、Recipeが宣言するPython依存（`pygame`、`PyYAML`）をFoundation Pythonへ入れます。この時点のdoctorは、次の手順で用意するdrone-coreのバイナリとMuJoCoを`MISSING`と報告します。

### 3. drone-coreのリリースバイナリとMuJoCoを用意する（初回のみ）

```bash
curl -L -o /tmp/hakoniwa-drone-core-mac.zip \
  https://github.com/toppers/hakoniwa-drone-core/releases/download/v4.1.1/mac.zip
unzip -o /tmp/hakoniwa-drone-core-mac.zip -d ../hakoniwa-drone-core
bash ../hakoniwa-drone-core/tools/install-mujoco-mac.bash ../hakoniwa-drone-core
bash ../hakoniwa-drone-core/tools/link-mujoco-mac.bash ../hakoniwa-drone-core/mac \
  --lib-dir "$(cd ../hakoniwa-drone-core && pwd)/vendor/mujoco/lib"
```

`mac.zip`は`hakoniwa-drone-core/mac/`に展開されます。配布バイナリには配布元のビルド環境のMuJoCoパスが埋め込まれているため、`link-mujoco-mac.bash`で、このチェックアウトの`vendor/mujoco/lib`をRPATHへ追加します。展開先を変える場合は、`tools/fpv.py`に`--drone-core-root`／`--drone-core-bin`を指定してください。

```bash
python3.12 tools/recipe.py doctor --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

すべて`SATISFIED`になれば準備完了です。

### 4. 機体を生成して起動する

```bash
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py configure
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py start
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py status
```

`configure`は既定のRecipeとWorldから機体を生成し、入力hashが一致する[検証済み構成](verified-configs/example-5inch-angle/)を自動適用します。

SpeedyBee Master3Xを飛ばす場合は、Master3XのRecipeと出力先を指定します。PID自動チューニング済みの[検証済み構成](verified-configs/master3x-angle/)が自動適用されます。`start`／`status`／`stop`にも同じ`--output`を付けてください。

```bash
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py configure \
  --recipe ../hakoniwa-fpv-drone/recipes/examples/master3x.yaml \
  --output ../hakoniwa-fpv-drone/build/master3x
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py start --output ../hakoniwa-fpv-drone/build/master3x
````start`でMuJoCo Viewerが開き、PS5コントローラの入力クライアントがバックグラウンドで起動します。ログは`build/example-5inch/runtime/logs/`に出力されます。

### 5. PS5で操縦する

1. **×ボタンを押して離す**：Radio Controlが有効になります（アーム）。押し続ける必要はありません。サービスログに`radio_control: 1`が出ます。
2. **△ボタンを押して離す**：初期のGPSモードからATTI（Angle）モードへ切り替わります。サービスログに`Control mode changed to ATTI`が出ます。
3. **左スティックを上へ倒す**：浮上します。

この機体は`ANGLE_CONTROL_ENABLE=1`のため、**GPSモードのままでは制御出力が出ず、×を押しただけでは浮上しません**。必ず△でATTIへ切り替えてください。

| スティック | 上下 | 左右 |
|---|---|---|
| 左 | スロットル（上昇・下降） | Yaw |
| 右 | Pitch（前進・後退） | Roll（左右移動） |

既定RC設定はDrone Coreの`drone_api/rc/rc_config/ps4-control.json`で、macOSのPS5 DualSenseにもこのマッピングを使います。別の設定は`--rc-config`で指定できます。OSやpygameの認識によってボタン番号が異なる場合は、RC設定を調整してください。

高度0.2m以下で左スティックを下へ倒し続けると、Landingへ遷移して着陸します。

### 6. 停止する

```bash
python3.12 ../hakoniwa-fpv-drone/tools/fpv.py stop
```

終了時は`hako-cmd stop`や`kill -9`ではなく、必ず`stop`でLauncherのterminate経路を使ってください。

### うまく動かないとき

- **×と△は効くのにスティックで何も起きない**：`build/example-5inch/runtime/logs/fpv-drone-service.out`に、`radio_control: 1`の直後の`[STATE] Hovering -> Landing`がないか確認してください。runtimeの`control-param.txt`に`CTRLMODE_LANDING_*`がないと、地上でRadio Controlを有効にした瞬間にLandingへ入り、抜けられなくなります。
- **`Drone Core service ... not found`**：手順3の展開先とリンクを確認してください。


## FPV機体のHover・Angle PID tuning

> **ライセンス:** PID自動チューニングを実行するには、箱庭ドローンPROライセンスが必要です。本リポジトリのCatalog／Recipe／Generatorを利用できることは、箱庭ドローンPROのPID自動チューニング機能を利用できることを意味しません。`tune-*`コマンドは`hakoniwa-drone-core`ではなく、別途`--drone-pro-root`で指定するビルド済み`hakoniwa-drone-pro`checkoutを使用します（既定は兄弟ディレクトリ）。

箱庭ドローンPROを利用すると、生成した機体ごとにHover／Angle PID候補を自動探索し、応答波形、hard gate、定量指標を使って比較できます。部品構成を変えるたびに感覚だけで調整をやり直すのではなく、入力モデルを固定した再現可能な評価工程にできます。今回のサンプル機体でも、生成、Hover調整、Angle調整、PS5実操作までを一貫して確認できました。

Angleモードは現在のDrone PROでは`AttiHover`として動作します。そのため、Angle PIDだけを直接探索せず、最初にHoverを確認してからAngleへ進みます。高度2・水平位置の段階はFPV MVPの対象外です。

```text
generated vehicle
  -> Hover check/tuning
  -> human review
  -> Angle tuning
  -> PS5 flight review
```

最初に、Drone PROが提供するmacOS用PID runnerをビルドします。

```bash
python3.12 tools/fpv.py tune-build
```

通常の`configure`で生成した機体を、変更不能なPID tuning profileへコピーします。profile名には、`drone_config_0.json`、`drone.xml`、`control-param.txt`から計算したhashが含まれます。物理モデルを変更した場合は、新しいprofileを作り直します。`tune-audit`は、Catalogから集計した質量、`drone_config_0.json`、`control-param.txt`の`MASS`、MuJoCoが実際に生成した剛体質量・COM・慣性、ローター座標（FLU→FRD変換後）を照合します。`tune-prepare`はこの監査を自動実行し、不整合があればprofileを作成しません。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py tune-audit
python3.12 tools/fpv.py tune-prepare --hover-trials 40
python3.12 tools/fpv.py tune-hover
```

監査結果は`build/<package>/runtime/vehicle/tuning-input-audit.json`に保存されます。`drone_config_0.json`の`inertia`が`[0, 0, 0]`の場合、これは欠損値ではなく、生成済み`drone.xml`の`inertiafromgeom`へ委譲する指定です。監査レポートには、そのMuJoCo実算値も記録されます。

FPV profileは、既存X500向けcanonical templateをそのまま流用せず、軽量機用のHover seed（`PID_ALT_Kp=4`、`PID_ALT_Kd=2`、`PID_ALT_SPD_Kp=2`、`PID_ALT_SPD_Kd=1`）を使います。Hover探索では垂直速度の`Kp`と`Kd`を探索し、既定で40 trialを実行します。`--hover-trials`で変更できます。

Hoverのhard gate、score、波形を確認して採用可能と判断した後だけ、Angleを実行します。

```bash
python3.12 tools/fpv.py tune-angle --angle-trials 40 --angle-refine
```

Angle結果を人間が確認した後、PS5実行用の`build/`へ一時適用します。Catalogや生成初期値は変更されません。

```bash
python3.12 tools/fpv.py tune-apply
python3.12 tools/fpv.py start
```

`tune-apply`の適用先は`build/<package>/runtime/vehicle/control-param.txt`だけです。`configure`を再実行すると生成初期値へ戻ります。

2026-08-29にPS5で確認したサンプル機体は、物理モデル・実行設定・PIDを`verified-configs/example-5inch-angle/`へ一体で固定しています。既定RecipeとWorldで`configure`すると、入力hashが一致する検証済み構成が自動適用されます。通常手順は次の2コマンドです。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py start
```

生成直後の未調整PIDを調査するときだけ`configure --generated-defaults`を指定します。`restore-verified-config`は、検証済み3ファイルを明示的に戻す保守用コマンドです。

結果は`hakoniwa-drone-pro/work/pid-tuning/fpv-<package>-<hash>/results/autotune/`へ出力されます。自動探索のbest candidateは採用決定ではありません。詳細な評価基準と生成物は、Drone PROの`pro-docs/control-link/pid-tuning.md`を正本とします。

チューニング開始後は、質量、慣性、Ct/Cq、ローター位置・回転方向・最大回転数、制御周期、シミュレーション周期を変更しないでください。

初回接続で判明したControllerの分離、地上静止の誤判定、MuJoCo／NED座標変換、FPV機向け探索範囲、結果判定の注意点は、[PIDチューニング接続ノウハウ](docs/pid-tuning-knowhow.md)にまとめています。探索範囲と試行結果はコミットしません。飛行確認済みPIDを保存する場合だけ、対応する物理モデル・実行設定と一体で`verified-configs/`へ固定します。

## 現在の制約

- `quad_x`、4モーターのみ
- Catalogはgenericな例であり、実在製品スペックではない
- フレーム形状はCADではなくbox proxy
- 非フレーム部品の慣性は配置点に置いたpoint mass近似
- 最大推力はCatalogの `Ct` と最大回転数による推定
- 飛行時間は未計算
- PIDは実機向け推奨値ではなく、シミュレーション開始用の初期値
- Angle設定生成は既存Radio Controllerへ接続可能
- Rate設定は生成できるが、現行Drone PROのRadio orchestratorにRate実行Profileを追加する必要がある
- Betaflight backend、GUI、実機ログ同定は未実装

## Roadmap

1. Generated PackageをDrone PROレシピから起動するTask 0
2. Drone PRO Radio orchestratorのRate/Acro Profile
3. FPV送信機入力とRate/Expo設定
4. カタログ互換性診断（電圧、プロペラ径、推力重量比等）
5. Three.js FPVカメラと機体外観adapter
6. PID tuning結果をGenerated Packageへ昇格するコマンド
7. 実測ログによるモデル補正
8. optionalなBetaflight backend

## ライセンス

このリポジトリのソフトウェア、Catalog、Recipe、およびドキュメントは[MIT License](LICENSE)で提供します。

MIT Licenseが適用されるのは`hakoniwa-fpv-drone`の成果物です。生成物を実行するHakoniwa Drone Core／PRO、PID自動チューニング、第三者の部品データ、モデル、ライブラリには、それぞれのライセンスと利用条件が適用されます。特にPID自動チューニングの実行には、有効な箱庭ドローンPROライセンスが必要です。
