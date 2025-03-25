<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns="http://www.opengis.net/citygml/2.0"
          xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
          xmlns:gml="http://www.opengis.net/gml">
    <cityObjectMember>
        <bldg:Building gml:id="BLDG_1">
            <bldg:measuredHeight>10.0</bldg:measuredHeight>
            <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
            <bldg:yearOfConstruction>1950</bldg:yearOfConstruction>
            <bldg:function>1000</bldg:function>
            <bldg:boundedBy>
                <bldg:GroundSurface>
                    <bldg:lod2MultiSurface>
                        <gml:MultiSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>0 0 0 0 10 0 10 10 0 10 0 0 0 0 0</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:MultiSurface>
                    </bldg:lod2MultiSurface>
                </bldg:GroundSurface>
            </bldg:boundedBy>
        </bldg:Building>
    </cityObjectMember>
</CityModel> 