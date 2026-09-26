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

## Quick Start（cloneからPS5操縦まで）

このリポジトリは[箱庭ビジネスパック](https://github.com/hakoniwalab/hakoniwa-business-pack)のWorkspaceで使います。Python環境はBusiness PackのFoundation Python（Python 3.12）に一本化し、個別のvenvは作りません。以下は、生成した機体をMuJoCo ViewerとPS5 DualSenseで操縦するまでの手順です。すべて箱庭ビジネスパックのWorkspace（`(hako)`シェル）から実行します。物理・制御ランタイムには無償版の[hakoniwa-drone-core](https://github.com/toppers/hakoniwa-drone-core) v4.1.1のリリースバイナリを使い、`hakoniwa-drone-pro`は不要です（PID自動チューニングだけはPROライセンスが必要です）。

前提：Python 3.12（Homebrew版は不可）、Xcode Command Line Tools、`brew install glfw`、PS5コントローラをBluetoothまたはUSBで接続済み。Business Pack側の前提は[Getting Started](https://github.com/hakoniwalab/hakoniwa-business-pack/blob/main/docs/getting-started-ja.md)を参照してください。飛行まで検証済みなのはmacOS（Apple Silicon）です。

Windows 11（x64）では、PowerShellで実行し、`python3.12`を`py -3.12`に読み替えます。コマンドが異なる箇所には、Windows（PowerShell）用のブロックを別に示します。PowerShellでは、行の継続に`\`ではなく`` ` ``（バッククォート）を使います。Windowsでは、事前にVisual Studio 2022（C++デスクトップ開発）と、自分でcloneしたvcpkgへBoostとGLFWを入れておきます（Business Pack Getting Startedの4.2）。

```powershell
git clone https://github.com/microsoft/vcpkg.git D:\vcpkg
D:\vcpkg\bootstrap-vcpkg.bat -disableMetrics
D:\vcpkg\vcpkg.exe install boost-asio:x64-windows boost-beast:x64-windows glfw3:x64-windows
```

vcpkgの場所は任意です。以降の例ではD:\vcpkgとします。

### 1. 2つのリポジトリを同じ親ディレクトリへcloneする

```bash
mkdir fpv-drone && cd fpv-drone
git clone https://github.com/hakoniwalab/hakoniwa-business-pack.git
git clone https://github.com/hakoniwalab/hakoniwa-fpv-drone.git
```

### 2. Workspaceに入る

```bash
cd hakoniwa-business-pack
python3.12 tools/workspace.py enter
```

Windows（PowerShell）：

```powershell
cd hakoniwa-business-pack
py -3.12 tools\workspace.py enter
```

プロンプトの先頭に`(hako)`が付きます。以降のコマンドはすべて、この`(hako)`シェルの`hakoniwa-business-pack`で実行します。別のvenvが有効な場合も、Workspaceが環境を切り替えるので影響はありませんが、先に`deactivate`しておくと確実です。

### 3. Recipeを診断し、Foundationと依存を構築する

```bash
python3.12 tools/recipe.py doctor    --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py plan      --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
python3.12 tools/recipe.py configure --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

Windows（PowerShell）では、`configure`の前にvcpkgの場所をFoundationへ登録します（Getting Startedの4.6）。WebBridgeのビルドがBoostを使うため、これを省くと`configure`が失敗します。

```powershell
py -3.12 tools\recipe.py doctor --recipe ..\hakoniwa-fpv-drone\recipes\business-pack\fpv-drone-design-angle-flight.yaml
py -3.12 tools\foundation.py toolchain --recipe-id fpv-drone-design-angle-flight --vcpkg-root D:\vcpkg
py -3.12 tools\recipe.py configure --recipe ..\hakoniwa-fpv-drone\recipes\business-pack\fpv-drone-design-angle-flight.yaml
```

最初の`doctor`は、Foundationがまだないので`MISSING`になります。これは正常です。`configure`は、不足している兄弟リポジトリ（`hakoniwa-core-pro`、`hakoniwa-pdu-python`、`hakoniwa-pdu-endpoint`、`hakoniwa-pdu-bridge-core`、`hakoniwa-drone-core` v4.1.1、`hakoniwa-threejs-drone`）をcloneし、Foundation（`work/foundation/install`）をビルドし、Recipeが宣言するPython依存（`pygame`、`PyYAML`、`trimesh`）をFoundation Pythonへ入れます。初回は10分以上かかります。完了すると、`(hako)`シェルの`python`はFoundation Pythonを指すので、以降は`python`で実行します。`configure`が最後に`Foundation: SATISFIED`で終わっていることを確認してください。終わっていないうちは、`python`はシステムのPythonのままで、手順5の`fpv.py`が`Foundation Python not found`で止まります。

drone-coreのリリースバイナリとMuJoCoは、cloneしただけでは入っていません。次の手順4で用意します。

### 4. drone-coreのリリースバイナリとMuJoCoを用意する

```bash
python ../hakoniwa-fpv-drone/tools/fpv-drone-core.py prepare
python tools/recipe.py doctor --recipe ../hakoniwa-fpv-drone/recipes/business-pack/fpv-drone-design-angle-flight.yaml
```

`fpv-drone-core.py prepare`は、OSに合ったdrone-core v4.1.1のリリースzip（macOSは`mac.zip`、Linuxは`lnx.zip`、Windowsは`win.zip`）とMuJoCoを、SHA-256を検証してダウンロードし、`hakoniwa-drone-core`へ展開・インストールします。macOSでは、配布バイナリに埋め込まれた配布元のMuJoCoパスに加えて、このチェックアウトの`vendor/mujoco/lib`をRPATHへ追加します。ダウンロードしたファイルは`hakoniwa-drone-core/vendor/downloads/`に保存され、再実行時は検証済みのファイルを再利用します。何度実行しても同じ状態になります。

`prepare`の最後に`[OK] Drone Core ...`と`[OK] MuJoCo ...`が出て、doctorですべて`SATISFIED`になれば準備完了です。

### 5. 機体を生成して起動する

5インチのサンプル機：

```bash
python ../hakoniwa-fpv-drone/tools/fpv.py configure
python ../hakoniwa-fpv-drone/tools/fpv.py start
python ../hakoniwa-fpv-drone/tools/fpv.py status
```

`configure`は既定のRecipeとWorldから機体を生成し、入力hashが一致する[検証済み構成](verified-configs/example-5inch-angle/)を自動適用します。

SpeedyBee Master3X：

```bash
python ../hakoniwa-fpv-drone/tools/fpv.py configure \
  --recipe ../hakoniwa-fpv-drone/recipes/examples/master3x.yaml \
  --output ../hakoniwa-fpv-drone/build/master3x
python ../hakoniwa-fpv-drone/tools/fpv.py start  --output ../hakoniwa-fpv-drone/build/master3x
python ../hakoniwa-fpv-drone/tools/fpv.py status --output ../hakoniwa-fpv-drone/build/master3x
```

Windows（PowerShell）：

```powershell
python ..\hakoniwa-fpv-drone\tools\fpv.py configure `
  --recipe ..\hakoniwa-fpv-drone\recipes\examples\master3x.yaml `
  --output ..\hakoniwa-fpv-drone\build\master3x
python ..\hakoniwa-fpv-drone\tools\fpv.py start  --output ..\hakoniwa-fpv-drone\build\master3x
python ..\hakoniwa-fpv-drone\tools\fpv.py status --output ..\hakoniwa-fpv-drone\build\master3x
```

PID自動チューニング済みの[検証済み構成](verified-configs/master3x-angle/)が自動適用されます。`stop`にも同じ`--output`を付けてください。

`start`でMuJoCo Viewerが開き、PS5コントローラの入力クライアントがバックグラウンドで起動します。ログは`<output>/runtime/logs/`に出力されます。

`configure`は、シミュレーション時刻を実時間に合わせる箱庭アセット（`tools/fpv_realtime_pacer.py`）もLauncherへ加えます。ドローンサービスはスリープせずに全速で動き、ペーサーが実際の経過時間に合わせて自分の時刻を進めます。箱庭のコンダクターは、最も遅いアセットから`max_delay`以上離れて世界時刻を進めないため、シミュレーションはOSによらず実時間の速さになります。`<output>/runtime/logs/fpv-realtime-pacer.out`に、5秒ごとの実時間比（`rtf`）が出ます。ペーサーのΔTは`--pacer-delta-msec`（既定10ms）で変えられます。デッドロックを避けるため、ドローンサービスのコンダクターの`max_delay`（20ms）以下にしてください。ペーサーを外す場合は`--no-realtime-pacer`を付け、代わりに`--real-sleep-msec`でステップごとのスリープを指定します。

`status`は、Launcherの状態に加えて、ログから読み取った今の状態と、次にすべき操作を表示します。

```text
Simulation    : running
Controller    : DualSense Wireless Controller
Radio Control : OFF
Mode          : GPS
Flight state  : Hovering
Next: press and release Cross to enable Radio Control.
```

### 6. PS5で操縦する

1. **×ボタンを押して離す**：Radio Controlが有効になります（アーム）。押し続ける必要はありません。サービスログに`radio_control: 1`が出ます。
2. **△ボタンを押して離す**：初期のGPSモードからATTI（Angle）モードへ切り替わります。サービスログに`Control mode changed to ATTI`が出ます。
3. **左スティックを上へ倒す**：浮上します。スティックを中央に戻すと、その高度でホバリングします。

この機体は`ANGLE_CONTROL_ENABLE=1`のため、**GPSモードのままでは制御出力が出ず、×を押しただけでは浮上しません**。必ず△でATTIへ切り替えてください。×と△は**押すたびに切り替わるトグル**で、画面には状態が表示されません。2回押すと元に戻るので、迷ったら別のターミナルで`status`を実行し、`Radio Control : ON`と`Mode : ATTI`になっているか確認してください。

| スティック | 上下 | 左右 |
|---|---|---|
| 左 | スロットル（上昇・下降） | Yaw |
| 右 | Pitch（前進・後退） | Roll（左右移動） |

既定RC設定はDrone Coreの`drone_api/rc/rc_config/ps4-control.json`で、macOSのPS5 DualSenseにもこのマッピングを使います。別の設定は`--rc-config`で指定できます。OSやpygameの認識によってボタン番号が異なる場合は、RC設定を調整してください。

高度0.2m以下で左スティックを下へ倒し続けると、Landingへ遷移して着陸します。

### 7. 停止する

```bash
python ../hakoniwa-fpv-drone/tools/fpv.py stop
python ../hakoniwa-fpv-drone/tools/fpv.py stop --output ../hakoniwa-fpv-drone/build/master3x   # Master3Xの場合
```

終了時は`hako-cmd stop`や`kill -9`ではなく、必ず`stop`でLauncherのterminate経路を使ってください。Workspaceを抜けるときは`exit`します。

### 8. Three.jsビューアで見る（任意）

MuJoCo Viewerに加えて、ブラウザのThree.jsビューアで機体とプロペラの回転を表示できます。Master3Xでは、Assembly Graphから機体ボディ・プロペラ・カメラのGLBを生成して表示します。手順3の`configure`で、WebBridge（`hakoniwa-pdu-bridge-core`）、`hakoniwa-threejs-drone`、`trimesh`はすでに用意されています。

```bash
python ../hakoniwa-fpv-drone/tools/fpv.py configure --threejs \
  --assembly ../hakoniwa-fpv-drone/recipes/examples/master3x-visual-demo.assembly.json \
  --output ../hakoniwa-fpv-drone/build/master3x
python ../hakoniwa-fpv-drone/tools/fpv.py start       --output ../hakoniwa-fpv-drone/build/master3x
python ../hakoniwa-fpv-drone/tools/fpv.py open-viewer --output ../hakoniwa-fpv-drone/build/master3x
```

Windows（PowerShell）：

```powershell
python ..\hakoniwa-fpv-drone\tools\fpv.py configure --threejs `
  --assembly ..\hakoniwa-fpv-drone\recipes\examples\master3x-visual-demo.assembly.json `
  --output ..\hakoniwa-fpv-drone\build\master3x
python ..\hakoniwa-fpv-drone\tools\fpv.py start       --output ..\hakoniwa-fpv-drone\build\master3x
python ..\hakoniwa-fpv-drone\tools\fpv.py open-viewer --output ..\hakoniwa-fpv-drone\build\master3x
```

`--threejs`の構成では、MuJoCo Viewerは開きません。両方を表示したい場合は、`configure`に`--mujoco-viewer`を付けてください。`--assembly`から生成したRecipeが`recipes/examples/master3x.yaml`と一致するため、チューニング済みの[検証済み構成](verified-configs/master3x-angle/)が自動適用されます。ブラウザが開いたら、左上の**connect**を押してください。WebSocket（`ws://127.0.0.1:28765`）につながり、Drone Stateに位置とpwm0〜3が表示され、プロペラが回ります。PS5の操作は手順6と同じです。停止は`stop --output ../hakoniwa-fpv-drone/build/master3x`です。

`--threejs`の構成では、HTTP（28000番）とWebSocket（28765番）のポートを使います。8000番や8765番のような定番の番号は、ほかのアプリやWindowsのサービスと衝突しやすいため避けています。別の番号にする場合は、`configure`に`--threejs-http-port`と`--threejs-ws-port`を指定してください。`start`はこれらのポートが空いているかを先に確認し、使用中の場合は使っているプロセスを表示して起動しません。

### うまく動かないとき

- **×と△は効くのにスティックで何も起きない**：`<output>/runtime/logs/fpv-drone-service.out`に、`radio_control: 1`の直後の`[STATE] Hovering -> Landing`がないか確認してください。runtimeの`control-param.txt`に`CTRLMODE_LANDING_*`がないと、地上でRadio Controlを有効にした瞬間にLandingへ入り、抜けられなくなります。
- **浮上しない**：`status`で`Radio Control : ON`と`Mode : ATTI`を確認してください。×と△はトグルなので、押し直すと元に戻ります。
- **`no game controller is connected`で`start`が止まる**：PS5コントローラを接続してから、もう一度`start`してください。`start`は、コントローラがないと起動しません。RCクライアントが終了して、全体が巻き込まれて止まるのを防ぐためです。
- **`... is in use by another Hakoniwa simulation`で`start`が止まる**：`start`は起動前に、前回の実行で残った箱庭のmmapファイル（Core configの`core_mmap_path`の`mmap-*.bin`）を削除します。Windowsでは、古いmmapファイルがサイズを変えずに再利用され、`hako-cmd`が落ちたり、アセットが`WAIT RUNNING`のまま止まったりするためです。このエラーは、別の箱庭シミュレーション（別のWorkspaceのものも含む）がそのファイルを使っているという意味です。そちらを`stop`してから、もう一度`start`してください。
- **機体の動きが遅い・速すぎる**：`fpv-realtime-pacer.out`の`rtf`が1.0付近か確認してください。ペーサーが起動していないと、ドローンサービスはスリープなしで全速になります。
- **浮上するがホバリングしない**：`configure`の出力が`No verified FPV config matches ...`になっていないか確認してください。未調整の汎用PIDが使われています。
- **`Drone Core service ... not found`**：手順4の`fpv-drone-core.py prepare`を実行してください。
- **`Foundation Python not found`**：手順3の`configure`が`Foundation: SATISFIED`まで完了していません。Windowsでは、`foundation.py toolchain`の登録を先に行ってください。
- **`[WARNING] Hakoniwa Workspace is not active`**：手順2の`(hako)`シェルの外で実行しています。
- **Three.jsビューアに機体の状態が出ない**：左上の**connect**を押したか確認してください。`start`が`port 28765 ... is in use`で止まる場合は、表示されたプロセスを止めるか、`configure`で別のポートを指定してから、もう一度`start`してください。

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

実行手順は[Three.jsビューアで見る](#8-threejsビューアで見る任意)を参照してください。

`open-viewer`は生成済みURLを既定ブラウザで自動的に開きます。Three.jsではMuJoCo runtimeモデルの`fpv`カメラ位置・向き・FOVを正本として、主観映像をメイン、操作可能な客観映像を左上PiPに表示します。`Tab`で主・副画面を交換し、`F`でPiPを表示・非表示にできます。

ブラウザでは既存のThree.js機体GLBを使い、`DroneVisualStateArray`の位置・姿勢・PWMから機体移動と4枚のプロペラ回転を表示します。外観モデル全体は、生成機体のモーター対角距離（wheelbase）とThree.js基準機体のwheelbaseから求めた倍率でスケールされます。世界座標やコースにはこの倍率を適用しません。

FPVコースはGLBとして二重管理せず、World YAMLを正本として`fpv-course.json`へ生成します。Three.js側の`environment.type: fpv-course`は明示指定時だけ有効で、従来のGLB/MJCF環境には影響しません。`--threejs`なしの通常手順も従来どおりです。

## Hakoniwa Business Packから利用する

FPV固有のComponent CatalogとVehicle Recipeはこのリポジトリを正本とします。Business Pack側にはコンポーネントの検索Catalogだけを置き、システム構成Recipeもこのリポジトリの[FPV設計・Angle飛行Recipe](recipes/business-pack/fpv-drone-design-angle-flight.yaml)を参照します。これにより、FPVの設定や実行手順を二重管理しません。

このRecipeを使った環境構築から飛行までの手順は、[Quick Start](#quick-startcloneからps5操縦まで)を参照してください。

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

## 生成ツールだけを使う

Quick Startの手順1〜3を終えたあと、機体の検証、BOM、生成パッケージだけを確認したい場合は、`(hako)`シェルの中で生成ツールを実行します。

```bash
cd ../hakoniwa-fpv-drone
export PYTHONPATH=src
python -m fpv_drone_generator.cli validate recipes/examples/5inch-fpv.yaml
python -m fpv_drone_generator.cli bom recipes/examples/5inch-fpv.yaml
python -m fpv_drone_generator.cli generate \
  recipes/examples/5inch-fpv.yaml \
  --world recipes/environments/fpv-training-course.yaml \
  --output build/example-5inch
```

Windows（PowerShell）：

```powershell
cd ..\hakoniwa-fpv-drone
$env:PYTHONPATH = "src"
python -m fpv_drone_generator.cli validate recipes\examples\5inch-fpv.yaml
python -m fpv_drone_generator.cli bom recipes\examples\5inch-fpv.yaml
python -m fpv_drone_generator.cli generate `
  recipes\examples\5inch-fpv.yaml `
  --world recipes\environments\fpv-training-course.yaml `
  --output build\example-5inch
```

## テスト

`(hako)`シェルの中で、このリポジトリのルートから実行します。

```bash
PYTHONPATH=src python -m unittest discover -v
```

Windows（PowerShell）：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -v
```

MuJoCo Python bindingがある環境では、生成XMLを `MjModel.from_xml_path()` でロードするテストも実行します。ない場合はその1件だけskipします。Three.jsアセット出力のテストは、`trimesh`がない環境ではskipします。

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

FPV用のtuning copyは高度2 mから開始します。各trialはDrone PRO標準評価に加え、FPV側で全シナリオの高度、接触回数、Motor Dutyを検査します。高度0.1 m未満、評価区間中の接触増加、Duty 0/1への飽和率10%超のいずれかを検出した候補は適用対象になりません。判定結果は`build/<package>/runtime/pid-tuning-<phase>-flight-gate.json`へ保存されます。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py tune-audit
python3.12 tools/fpv.py tune-prepare --hover-trials 40
python3.12 tools/fpv.py tune-hover
```

監査結果は`build/<package>/runtime/vehicle/tuning-input-audit.json`に保存されます。`drone_config_0.json`の`inertia`が`[0, 0, 0]`の場合、これは欠損値ではなく、生成済み`drone.xml`の`inertiafromgeom`へ委譲する指定です。監査レポートには、そのMuJoCo実算値も記録されます。

FPV profileは、既存X500向けcanonical templateの姿勢ゲインをそのまま流用しません。Hover段階では5inch機で飛行実績のある保守的な姿勢基準（Rate Kp/Ki/Kd = `0.15/0.08/0.005`、Angle Kp/Ki/Kd = `6/0.5/0.75`）へ固定し、垂直速度の`Kp`と`Kd`だけを探索します。姿勢系を探索するのは次のAngle段階です。この段階分離により、不安定な内側姿勢ループを高度PIDの良否として誤評価することを防ぎます。自由空間開始時の初期姿勢過渡を考慮し、Hover entry hard gateはFPV profile内で5秒に設定します。Hoverは既定で40 trialを実行し、`--hover-trials`で変更できます。

Hoverのhard gate、score、波形を確認して採用可能と判断した後だけ、Angleを実行します。

```bash
python3.12 tools/fpv.py tune-angle --angle-trials 40 --angle-refine
```

`--angle-refine`は、飛行実績のある5inch PIDを含む低ゲイン範囲（Rate Kp 0.1–0.6、Rate Kd 0–0.03、Angle Kp 3–10）を探索します。旧Master3X trial 59周辺の高ゲイン範囲は使用しません。

Angle候補の選択後、地面を含む同じMuJoCoモデルで15秒の最終Hover検証を自動実行します。2秒後から10秒間、垂直速度±0.15 m/s、Roll/Pitch±2度を維持し、同時にFPV flight gateも通過する必要があります。結果は`build/<package>/runtime/pid-tuning-post-angle-hover.json`へ保存され、この検証が失敗すると`tune-angle`は成功になりません。

Angle結果を人間が確認した後、PS5実行用の`build/`へ一時適用します。Catalogや生成初期値は変更されません。

```bash
python3.12 tools/fpv.py tune-apply
python3.12 tools/fpv.py start
```

`tune-apply`はAngleのFPV flight gateを通過した選択結果だけを、`build/<package>/runtime/vehicle/control-param.txt`へ適用します。`configure`を再実行すると生成初期値へ戻ります。

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
