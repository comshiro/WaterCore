### Resources
ESA WorldCover (Land Cover): This is a thematic map. It classifies every pixel on Earth into one of 11 categories (e.g., Cropland, Tree cover, Built-up, Grassland). It’s used to study biodiversity, urban growth, and deforestation.
+2

Copernicus DEM (Elevation): This is a topographic model (specifically a Digital Surface Model or DSM). It provides a numerical value representing the height of the Earth's surface relative to sea level. It includes "surface" features like buildings and tree canopies. It’s used for flood modeling, flight safety, and engineering.

Global configuration: risk_assesment.ipynb:43-53
Defines catalog URL, collection names, training area bbox, candidate asset keys, and NDWI wet threshold.
Important: worldcover_collection is currently set to esa_worldcover, but the MPC collection name is typically esa-worldcover.

### Functions
search_items: risk_assesment.ipynb:63-75
Purpose: query STAC by collection, bbox, optional datetime/query filters.
Returns: list of matching items.
Behavior: raises ValueError if no items found, which is good for fail-fast debugging.

pick_asset_key: risk_assesment.ipynb:85-91
Purpose: from one STAC item, choose the first available asset key from your candidate list.
Returns: asset key string.
Behavior: raises KeyError with available keys if none match.

open_asset_and_clip: risk_assesment.ipynb:101-113
Purpose: sign MPC asset URL, open raster, clip to bbox.
Good point: includes crs="EPSG:4326" in clip_box as required.
Returns: clipped DataArray.

mossaic_collection: risk_assesment.ipynb:123-139
Purpose: load and clip each item, then mosaic all layers.
Flow: loops items, selects asset key, clips, appends to list, merges at end.

sentinel_monthly_ndwi: risk_assesment.ipynb:149-179
Purpose: build a monthly NDWI composite from Sentinel-2 scenes.

Flow:
Search low-cloud scenes
Sort by cloud cover and limit count
Read green (B03) and NIR (B08)
Reproject NIR to match green if needed
Compute NDWI = (green - nir) / (green + nir)
Stack scenes and take median composite
Returns: one NDWI raster for the month.

make_flood_mask: risk_assesment.ipynb:189-198
Purpose: create binary flood target from NDWI change.

Logic:
Align flood NDWI to baseline grid
wet_before = baseline > threshold
wet_after = flood > threshold
flood pixel = dry before AND wet after
Returns: uint8 mask with 0/1.

compute_slope_degrees: risk_assesment.ipynb:208-224
Purpose: compute slope from DEM via spatial gradients.
Math:
Get pixel resolution from transform
Compute dz/dx and dz/dy using np.gradient
Slope angle = arctan(sqrt((dz/dx)^2 + (dz/dy)^2)) converted to degrees

load_dem_and_worldcover: risk_assesment.ipynb:234-242
Purpose: fetch DEM and WorldCover items and mosaic both.
Returns: dem, wc.
Current runtime error comes from this path because worldcover collection name does not return items with current value.

align_training_layers: risk_assesment.ipynb:252-261
Purpose: align DEM and land cover to Sentinel template grid, compute slope, flag built-up class 50.

training_dataframe: risk_assesment.ipynb:271-287
Purpose: flatten aligned rasters to tabular samples.
Flow:
Reshape elevation/slope/landcover/flood to 1D
Keep only finite values
Build DataFrame with 3 features and flood target
Returns: clean training table.

train_rf: risk_assesment.ipynb:297-318
Purpose: train and evaluate RandomForest classifier.
Flow:
Ensure target has both classes
Split train/test with stratification
Fit model
Predict probabilities
Report classification metrics and ROC-AUC

build_feature_matrix: risk_assesment.ipynb:328-341
Purpose: build inference matrix for predict_risk.
Intended: stack valid elevation, slope, landcover vectors column-wise.

predict_risk: risk_assesment.ipynb:351-374
Purpose: API-core inference function.
Flow:

Load DEM and WorldCover for new bbox
Align DEM to landcover grid
Compute slope
Build feature matrix
Predict flood probability per valid pixel
Rebuild 2D heatmap
Return DataArray with geospatial coords/CRS
This is the correct high-level structure for API integration.

main pipeline: risk_assesment.ipynb:384-408
Orchestrates everything:
Open catalog
Generate May 2023 and May 2024 NDWI
Build flood mask
Load and align DEM/WorldCover
Build training table
Train model
Predict risk heatmap
Plot with matplotlib