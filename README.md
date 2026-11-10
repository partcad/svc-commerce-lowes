# //pub/svc/commerce/lowes

The Lowe's online store.

This package can be used for cost estimates for assemblies that use Lowe's
products. Placing orders is not implemented yet.

### Quotes

The provider `lowes` quotes any part declared with `vendor: lowes` and a
SKU, in this package or any other. A quote is what the products cost at one
Lowe's store, as their product pages on lowes.com say: each SKU in the cart
is found at lowes.com, priced once, and multiplied by the number of it to
order (whole packs, per `count_per_sku`); the quote is the sum. A product
page is read for its JSON-LD offer first and for the state the page's own
scripts start from second, and is only taken for the SKU's if it names the
SKU. Pages are kept for a day, separately for each store.

A SKU here is the Lowe's product ID: the number a product page's URL ends
with (`https://www.lowes.com/pd/<name>/<product ID>`), which is what Lowe's
own structured data calls the SKU. An item number ("Item #") or a model
number works too, as long as a search for it at lowes.com leads to the one
product.

lowes.com sits behind bot protection, and when that turns a request away
the quote fails, saying so, rather than coming back with a price that is
not one.

### Dimensional lumber

Lumber and plywood are published as aliases of the sizes the standard
names in `//pub/std/imperial/dimensional-lumber/stock`, each with the SKU
it is sold under. The geometry is the standard's, in its frame (width
along X, length along Y, thickness along Z).

| Part                | Product                                                    | Standard size     | SKU        |
|---------------------|------------------------------------------------------------|-------------------|------------|
| `lumber/2x4x8`      | Top Choice 2-in x 4-in x 8-ft #2 Southern Yellow Pine      | `lumber/2x4x8`    | 1001854134 |
| `lumber/2x4x12`     | Top Choice 2-in x 4-in x 12-ft #2 & Better Spruce Pine Fir | `lumber/2x4x12`   | 1001041436 |
| `lumber/2x6x8`      | Top Choice 2-in x 6-in x 8-ft #2 Fir                       | `lumber/2x6x8`    | 4082904    |
| `lumber/4x4x8`      | 4-in x 4-in x 8-ft #2 & Better Douglas Fir (green)         | `lumber/4x4x8`    | 1000028905 |
| `plywood/23-32x4x8` | 23/32-in x 4-ft x 8-ft Southern Yellow Pine BC Sanded      | `plywood/3-4x4x8` | 1003140514 |

A part cut to size names the standard size as its stock, and lists this
store among its package's `suppliers:`. Being an alias of that size is what
makes this store a place to buy it, and any other store that publishes an
alias of the same size is one too (Home Depot does), so the part is bought
from whichever of them is asked:

```yaml
manufacturing:
  method: subtractive
  source: //pub/std/imperial/dimensional-lumber/stock:lumber/4x4x8
  cut:
    cuts:
      - along: +Y
        length: $length in
```

Naming the product here instead (`//pub/svc/commerce/lowes:lumber/4x4x8`)
still works, and buys it here first. Being bought through an alias needs
PartCAD 0.10.8 or later.

The generic templates `dimensional-lumber` and `plywood` are still here:
the store's products of any size, with the vendor and **no SKU**, since
there is nothing to order until a size is chosen.

### Screws for wood

The screws `//pub/furniture/workspace/basic` is put together with, which
Home Depot's package draws: each is an alias of Home Depot's part, with
the SKU Lowe's sells it under and as many as come with it.

| Part                 | Product                                                          | SKU        | In a box |
|----------------------|------------------------------------------------------------------|------------|----------|
| `screws/sdws22600db` | Simpson Strong-Tie Strong-Drive SDWS Timber 0.220 x 6-in (SDWS22600DB-RP1) | 1002703110 | 1        |
| `screws/spax-8x2`    | SPAX #8 x 2-in Yellow Zinc Flat Head Interior Wood Screws        | 5001699237 | 161      |

### Choosing a store

Prices differ from one store to the next. Quotes are for the store the
provider's `storeNumber` names, Lowe's of Mooresville, NC unless it is told
otherwise. Ask a store of your own with a provider of your own:

```yaml
providers:
  lowes-near-me:
    type: enrich
    source: //pub/svc/commerce/lowes:lowes
    with:
      storeNumber: "1234"
      zipCode: "12345"
```

### Development

The provider is `lowes.py`. Its tests run it the way PartCAD does, against
pages made up in the shapes lowes.com uses, and ask lowes.com for nothing:

```shell
$ pip install pytest -r requirements.txt
$ python -m pytest tests
```


## Usage
Get an estimate for an 8 ft. 4x4:

```shell
$ pc supply quote --provider lowes lumber/4x4x8
```

The quote's cart ID is `None`: nothing is put in a cart at lowes.com. Add
`--json` for the price of each SKU and the product page it was read from:

```shell
$ pc -q supply quote --json --provider lowes lumber/2x4x8#6 lumber/4x4x8#4
```

Get an estimate for 20 M4 hex nuts, which come in packs of 16 (two packs):

```shell
$ pc supply quote --provider lowes hardware/fasteners/nuts/hex_nuts/4_mm_0_7_zinc_plated_steel_hex_nut_16_count#20
```


<br/><br/>

*Generated by [PartCAD](https://partcad.org/)*
