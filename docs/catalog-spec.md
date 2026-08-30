# Catalog仕様

各ファイルは次の共通形です。

```yaml
schema_version: 1
kind: motor
items:
  - id: generic_motor
    name: Generic Motor
    vendor: null
    description: Example
    metadata:
      value_origin: generic_example
```

## 共通属性

| 属性 | 必須 | 意味 |
|---|---:|---|
| `id` | yes | Recipeが参照する安定ID |
| `name` | yes | 表示名 |
| `vendor` | no | 不明ならnull/省略可能 |
| `description` | yes | 値の性質や注意 |
| `metadata` | no | Generatorが無視できる拡張情報 |

単位はキー名に含めます。Catalog v1では暗黙のmm、g、rpmを使用しません。

## 物理属性

- frame: `mass_kg`, `dimensions_m`, `wheelbase_m`
- motor: `mass_kg`, `kv_rpm_per_v`, optional `max_current_a`, `dynamics`
- propeller: `mass_kg`, `diameter_m`, `pitch_m`, `blade_count`, `thrust_coefficient_ns2_rad2`, `torque_coefficient_nms2_rad2`
- battery: `mass_kg`, `dimensions_m`, `cell_count`, `nominal_voltage_v`, `capacity_ah`, optional `internal_resistance_ohm`
- camera: `mass_kg`, `dimensions_m`, optional `fov_deg`
- controller: `mass_kg`, `backend`, `supported_modes`, `default_mode`, `parameters`
- landing_gear: `mass_kg`, `geometry`
- attachment: `mass_kg`, `physical_role`, `geometry`

frameはoptional `motor_mount_positions_m`と`geometry`を持てます。mount位置はMuJoCo FLU上の物理取付位置であり、回転方向やDrone PRO FRD配置の正本ではありません。v2 Recipeでは`rotor_layout`のMuJoCo位置と同じ順序・値でなければエラーにします。

## Primitive assembly

物理部品の形状は、製品固有の処理を追加せずprimitiveの集合で表現できます。

```yaml
geometry:
  visual:
    - name: antenna
      type: cylinder
      center_m: [0.0, 0.0, 0.03]
      radius_m: 0.003
      length_m: 0.06
      rpy_deg: [0.0, 0.0, 0.0]
      rgba: [0.05, 0.05, 0.05, 1.0]
  collision: []
  inertial:
    - name: mass_proxy
      type: cylinder
      center_m: [0.0, 0.0, 0.03]
      radius_m: 0.003
      length_m: 0.06
```

- shape: `box`, `cylinder`, `capsule`, `sphere`
- box寸法: `dimensions_m`は全寸法
- cylinder/capsule: `length_m`は軸方向の全長としてMuJoCo half-lengthへ変換
- 角度: degree
- visualは衝突無効、collisionは衝突有効で、どちらも質量0
- inertialは不可視・衝突無効。複数primitiveの総体積から共通密度を自動計算し、合計質量をCatalogの`mass_kg`へ一致させる
- v2では`inertia_kg_m2`や`center_of_mass_m`をユーザーに入力させない。MuJoCoがinertial geometryからCOMと慣性を導出する
- frameの`inertia_kg_m2`読み取りは既存v1 Catalog互換のみに残し、新規v2定義では使用しない

`attachment.physical_role: visual_only` は外観だけを追加し、独立質量をBOM合計へ加えません。外観部品の質量をframeへまとめている場合の二重計上防止に使います。

推力係数は無次元係数ではなく、Drone PROが使用する次元付き係数です。

```text
thrust_N = Ct * omega_rad_s^2
torque_Nm = Cq * omega_rad_s^2
```

由来不明の実在製品値を登録しません。サンプルは `generic_example` と明記しています。

## 制御値の由来

各parameterは値とoriginを持ちます。

- `generic_default`: 一般的な実行既定値
- `catalog_default`: Controller Catalogが提供する初期値
- `generated_initial`: 機体Recipeの解決結果からGeneratorが上書きする値

この分類は `control-param.json` に保存されます。

## Catalog rootの合成

公開Catalogへ非公開製品値をコピーせず、`--catalogs`を複数指定できます。

```bash
fpv-drone \
  --catalogs ./catalogs \
  --catalogs ../hakoniwa-drone-pro/tuning/x500/vehicle/catalogs \
  generate recipe.yaml --output build/vehicle \
  --drone-pro-rotor-contract ../hakoniwa-drone-pro/config/contracts/rotor-layout-v1.json
```

後続rootは必要なkindのYAMLだけを持つpartial catalogにできます。同じkindのitemは結合されます。同一IDの重複は暗黙にoverrideせずエラーにし、どちらの値が採用されたか曖昧になることを防ぎます。
