# hakoniwa-fpv-drone

> 組む前に飛ばす。

`hakoniwa-fpv-drone` は、FPVドローンの部品カタログと機体Recipeから、仮想BOM、物理特性、MuJoCoモデル、Hakoniwa Drone PRO設定を生成する機体構成・モデル生成ツールです。

Betaflightの再実装でも、操縦練習ゲームでもありません。部品を購入して組み立てる前に、候補構成を仮想的に組み、質量・重心・慣性・推力重量比などを確認し、簡易制御で試験する設計プロセスを作ることが目的です。

## Hakoniwa Drone PROとの関係

このリポジトリは設計入力と生成処理を管理し、[TOPPERS/hakoniwa-drone-core](https://github.com/toppers/hakoniwa-drone-core)を基盤とする箱庭ドローンPROを物理・制御ランタイムとして使用します。

- 本リポジトリ: Catalog、Recipe、物理モデルCompiler、生成Package
- Drone PRO: MuJoCo機体物理、Rotor/Battery、Mixer、Radio Controller、Rate/Angle PID、箱庭連携
- Three.js: FPVカメラ表示の将来backend。MVPではカメラの質量・外形・FOV・位置をメタデータとして生成します

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

Python 3.10以上を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

```bash
fpv-drone validate recipes/examples/5inch-fpv.yaml
fpv-drone bom recipes/examples/5inch-fpv.yaml
fpv-drone generate \
  recipes/examples/5inch-fpv.yaml \
  --output build/example-5inch
```

開発時はインストールせず、次の形式でも実行できます。

```bash
PYTHONPATH=src python -m fpv_drone_generator.cli validate recipes/examples/5inch-fpv.yaml
```

## CatalogとRecipe

Catalogは部品そのものです。

```text
catalogs/
├── frames.yaml
├── motors.yaml
├── propellers.yaml
├── batteries.yaml
├── cameras.yaml
└── controllers.yaml
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

詳しくは[Catalog仕様](docs/catalog-spec.md)と[Recipe仕様](docs/recipe-spec.md)を参照してください。

## Hakoniwa Business Packから利用する

FPV固有のComponent CatalogとVehicle Recipeはこのリポジトリを正本とします。Business Pack側にはコンポーネントの検索Catalogだけを置き、システム構成Recipeもこのリポジトリの[FPV設計・Angle飛行Recipe](recipes/business-pack/fpv-drone-design-angle-flight.yaml)を参照します。これにより、FPVの設定や実行手順を二重管理しません。

兄弟ディレクトリに`hakoniwa-business-pack`がある場合、Business Packの共通入口からガイド、診断、構築計画を利用できます。

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

## Angleモードで実行する

兄弟ディレクトリにビルド済みの`hakoniwa-drone-pro`と、Business Pack Foundation環境があるmacOSでは、生成PackageをMuJoCo ViewerとPS4/PS5入力へ接続できます。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py start
python3.12 tools/fpv.py status
python3.12 tools/fpv.py stop
```

`start`はバックグラウンドLauncherを使用します。終了時は`hako-cmd stop`や`kill -9`ではなく、必ず上記の`stop`でLauncherのterminate経路を使用してください。

既定RC設定はDrone PROの`drone_api/rc/rc_config/ps4-control.json`です。macOSではPS5 DualSenseにもこのマッピングを利用します。別設定は`--rc-config`で指定できます。

既定マッピングは、左スティック上下がスロットル、左右がYaw、右スティック上下がPitch、左右がRollです。ボタンindex 0（通常は×ボタン）を一度押して離すとRadio Controlの有効／無効が切り替わります。押し続ける必要はありません。OS／pygameの認識によってボタン番号が異なる場合はRC設定を調整してください。

## FPV機体のHover・Angle PID tuning

> **ライセンス:** PID自動チューニングを実行するには、箱庭ドローンPROライセンスが必要です。本リポジトリのCatalog／Recipe／Generatorを利用できることは、箱庭ドローンPROのPID自動チューニング機能を利用できることを意味しません。

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

通常の`configure`で生成した機体を、変更不能なPID tuning profileへコピーします。profile名には、`drone_config_0.json`、`drone.xml`、`control-param.txt`から計算したhashが含まれます。物理モデルを変更した場合は、新しいprofileを作り直します。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py tune-prepare
python3.12 tools/fpv.py tune-hover
```

Hoverのhard gate、score、波形を確認して採用可能と判断した後だけ、Angleを実行します。

```bash
python3.12 tools/fpv.py tune-angle
```

Angle結果を人間が確認した後、PS5実行用の`build/`へ一時適用します。Catalogや生成初期値は変更されません。

```bash
python3.12 tools/fpv.py tune-apply
python3.12 tools/fpv.py start
```

`tune-apply`の適用先は`build/<package>/runtime/vehicle/control-param.txt`だけです。`configure`を再実行すると生成初期値へ戻ります。

結果は`hakoniwa-drone-pro/work/pid-tuning/fpv-<package>-<hash>/results/autotune/`へ出力されます。自動探索のbest candidateは採用決定ではありません。詳細な評価基準と生成物は、Drone PROの`pro-docs/control-link/pid-tuning.md`を正本とします。

チューニング開始後は、質量、慣性、Ct/Cq、ローター位置・回転方向・最大回転数、制御周期、シミュレーション周期を変更しないでください。

初回接続で判明したControllerの分離、地上静止の誤判定、MuJoCo／NED座標変換、FPV機向け探索範囲、結果判定の注意点は、[PIDチューニング接続ノウハウ](docs/pid-tuning-knowhow.md)にまとめています。機体固有のPID値、探索範囲、試行結果はコミット対象にしません。

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
