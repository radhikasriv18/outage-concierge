import geopandas as gpd

homes = gpd.read_file("../aep_data/data/extracted/Data1/Customer_Clip.shp")
print(homes.columns.tolist())
print(homes.head(3).T)
print(homes["special_op"].value_counts())
print(homes["customer_c"].value_counts())