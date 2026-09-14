# Catalog Source / Product Boundary

FPV product information starts in a non-standard external world: manufacturer product pages, manuals, datasheets, and other documents. Hakoniwa does not treat those pages as Catalog data directly.

The repository separates that analog-facing evidence from the normalized digital Catalog:

```text
manufacturer page / manual / datasheet
                |
                v
catalogs/sources/**          analog-facing references
                |
                | AI-assisted extraction / human review
                v
catalogs/products/**         normalized Hakoniwa product data
                |
                v
Catalog loader -> Interface variants -> Assembly Graph -> Generator
```

## `catalogs/sources/`: analog-facing references

A source file is deliberately small. It identifies one product and records where the external evidence lives; it does not duplicate product specifications.

```yaml
schema_version: 1
kind: catalog-source
product_id: iflight_xing2_2207_1855kv
product_kind: motor
sources:
  - url: https://example.com/manufacturer/product
    role: manufacturer_product
  - url: https://example.com/manufacturer/manual.pdf
    role: manufacturer_manual
```

The schema is `schemas/catalog-source.schema.json`.

This layer is the intended input boundary for a future AI extractor. Web pages remain non-standard; the AI-assisted step interprets them and proposes a normalized product fragment for review.

## `catalogs/products/`: normalized digital products

Each real product is stored as one file so Catalog growth does not turn the legacy per-kind YAML files into large merge-conflict hotspots.

```text
catalogs/products/
  frames/<vendor>/<product>.yaml
  motors/<vendor>/<product>.yaml
  propellers/<vendor>/<product>.yaml
  batteries/<vendor>/<product>.yaml
  cameras/<vendor>/<product>.yaml
```

A product fragment contains exactly one normalized Catalog item and a mandatory `source_ref`:

```yaml
schema_version: 1
kind: motor
source_ref: sources/motors/iflight/xing2-2207-1855kv.yaml
item:
  id: iflight_xing2_2207_1855kv
  name: iFlight XING2 2207 1855KV
  ...
```

The schema is `schemas/catalog-product-fragment.schema.json`.

The Catalog loader verifies that:

- `source_ref` stays inside the same Catalog root;
- the referenced source file exists;
- source and product agree on `product_id` and `product_kind`;
- product IDs remain unique across legacy monolith files, product fragments, and additional Catalog roots.

## Migration and compatibility

Legacy files such as `frames.yaml`, `motors.yaml`, and `batteries.yaml` remain supported. The loader composes both forms:

```text
legacy <kind>.yaml
+
products/<kind>/**/*.yaml
```

This lets generic examples remain in the current monolith files while commercial products move to one-product-per-file storage. New commercial products should use `sources/` + `products/`.

## AI boundary

The intended automated workflow is:

```text
1. Human adds a small source file containing manufacturer URLs.
2. AI reads those external sources and creates/updates a product fragment draft.
3. Schema and Catalog validation run deterministically.
4. A human reviews provenance, derived values, estimates, and Interface variants.
5. The normalized product is merged and becomes ordinary Hakoniwa Catalog data.
```

The AI step is intentionally outside the authoritative Catalog loader. The loader only accepts already-normalized digital data and never scrapes or interprets manufacturer pages at runtime.
