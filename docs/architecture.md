# アーキテクチャ

## 目的

本プロジェクトの中心はYAMLの書式ではなく、部品情報をHakoniwa/MuJoCoで実行可能な物理機体へ変換するPhysical Vehicle Model Compilerです。

```text
Catalog ─┐
         ├─ Resolver ─> ResolvedVehicle ─┬─ MuJoCo renderer <─ World/Course YAML
Recipe  ─┘                               ├─ Drone PRO config renderer
                                         ├─ Controller param renderer
                                         └─ BOM/report renderer
```

## 境界

### Catalog

利用可能な部品の属性です。IDはRecipeから参照されます。Catalogファイルに将来属性を追加できるよう、共通属性以外の未知フィールドを許容します。Generatorが物理計算に使う必須属性はtyped dataclassへ変換します。

### Recipe

一台の機体について「どの部品を何個使い、どこへ置き、どの制御modeを使うか」を定義します。Catalogレコードのコピーではありません。

### Resolved Vehicle Model

`ResolvedVehicle` はbackend非依存の中間表現です。Catalogの生dictをrendererへ渡しません。typed components、BOM総質量、配置、Rotor配置、推力推定、近似一覧を保持します。v2の剛体COM・慣性はここで計算せず、MuJoCoへ委譲します。

### World / Course

World YAMLは、機体とは独立にMuJoCoの背景、照明、地面、物理障害物を定義します。同じ機体を複数コースで評価する場合も、同じコースで機体候補を比較する場合も、Vehicle Recipeを書き換えません。

### Generated Package

実行backend固有の成果物です。現行MVPはMuJoCoとHakoniwa Drone PROを対象にします。将来のBetaflightやThree.js接続は新renderer/adapterとして追加し、CatalogとRecipeを変更しません。

## 公開ツールと非公開機体定義の境界

Generator、スキーマ、汎用fixtureはこのMITリポジトリで管理します。製品固有・非公開の機体値は外部Catalog rootとRecipeから入力でき、公開Catalogへコピーする必要はありません。

```text
public generator + schema
          +
private catalogs + recipe
          ↓
deterministic generated vehicle package
```

Generatorは機体名で分岐しません。新しい機体はCatalog assembly、取付位置、Recipeで表現します。生成XMLには時刻や絶対パスを埋め込まず、同じ入力からbyte-identicalなMJCFを生成できます。

Drone PRO接続用のtarget contractは公開Generatorに同梱します。Recipe v2は正規FLU位置を一度だけ記述し、target adapterがcontractの変換行列に従ってFRD位置を生成します。`--drone-pro-rotor-contract`は新しい契約を検証するための明示overrideで、通常生成では同梱contractを使います。

## Drone PRO調査結果

| 生成物 | Drone PRO側の契約 |
|---|---|
| `drone.xml` | `components.droneDynamics.mujoco.modelPath` |
| body | `modelName: drone_base` |
| rotor bodies | `propNames: [prop1..prop4]` |
| physical config | `components.droneDynamics`, `rotor`, `thruster`, `battery` |
| controller | `moduleName: RadioController`, `backendType: adapter-hakoniwa` |
| runtime params | `controller.paramFilePath`が指すkey/valueテキスト |
| mode | `ANGLE_CONTROL_ENABLE`, `ANGLE_RATE_CONTROL_ENABLE` |

`controller.moduleDirectory` は現行factoryで不要なため生成しません。設定パスはPackage内の相対パスにしています。

## Rate/Angle backend

CatalogとRecipeは `rate` と `angle` を表現できます。ただし調査時点のDrone PRO Radio orchestratorはAngle経路を持つ一方、`ANGLE_RATE_CONTROL_ENABLE=true` は `Unknown` profileとして残っています。そのためMVPサンプルはAngleです。Rate生成契約は固定し、Drone PRO側の不足を明示しています。

## YAGNI

- Jinja2は導入せず、MuJoCo XMLは標準ライブラリのElementTreeで生成
- JSON Schemaは公開契約として置くが、CLIはtyped loaderで意味検証
- backend frameworkは作らず、renderer moduleの分離に留める
- 汎用剛体assembly solverやCAD importerは作らない
