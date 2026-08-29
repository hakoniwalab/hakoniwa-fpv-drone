# Catalog仕様 v1

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

- frame: `mass_kg`, `dimensions_m`, `wheelbase_m`, optional `inertia_kg_m2`
- motor: `mass_kg`, `kv_rpm_per_v`, optional `max_current_a`, `dynamics`
- propeller: `mass_kg`, `diameter_m`, `pitch_m`, `blade_count`, `thrust_coefficient_ns2_rad2`, `torque_coefficient_nms2_rad2`
- battery: `mass_kg`, `dimensions_m`, `cell_count`, `nominal_voltage_v`, `capacity_ah`, optional `internal_resistance_ohm`
- camera: `mass_kg`, `dimensions_m`, optional `fov_deg`
- controller: `mass_kg`, `backend`, `supported_modes`, `default_mode`, `parameters`

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
