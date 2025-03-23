<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
           xmlns:gml="http://www.opengis.net/gml"
           xmlns:gen="http://www.opengis.net/citygml/generics/1.0"
           xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0">
    <gml:boundedBy>
        <gml:Envelope srsName="EPSG:31256">
            <gml:lowerCorner>0 0</gml:lowerCorner>
            <gml:upperCorner>100 100</gml:upperCorner>
        </gml:Envelope>
    </gml:boundedBy>
    <cityObjectMember>
        <bldg:Building gml:id="BLDG_00001">
            <bldg:measuredHeight>10.5</bldg:measuredHeight>
            <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
            <bldg:function>residential</bldg:function>
            <bldg:yearOfConstruction>1990</bldg:yearOfConstruction>
            <bldg:address>
                <xAL:AddressDetails>
                    <xAL:ThoroughfareName>Teststraße</xAL:ThoroughfareName>
                    <xAL:BuildingNumber>42</xAL:BuildingNumber>
                    <xAL:PostalCode>1234</xAL:PostalCode>
                    <xAL:LocalityName>Teststadt</xAL:LocalityName>
                    <xAL:CountryName>Österreich</xAL:CountryName>
                </xAL:AddressDetails>
            </bldg:address>
            <gen:stringAttribute name="owner">
                <gen:value>Max Mustermann</gen:value>
            </gen:stringAttribute>
            <gen:intAttribute name="renovationYear">
                <gen:value>2010</gen:value>
            </gen:intAttribute>
            <gen:doubleAttribute name="energyRating">
                <gen:value>2.5</gen:value>
            </gen:doubleAttribute>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:CompositeSurface>
                    </gml:exterior>
                </gml:Solid>
            </bldg:lod2Solid>
        </bldg:Building>
    </cityObjectMember>
    <cityObjectMember>
        <bldg:Building gml:id="BLDG_00002">
            <bldg:measuredHeight>15.0</bldg:measuredHeight>
            <bldg:function>commercial</bldg:function>
            <bldg:lod2MultiSurface>
                <gml:MultiSurface>
                    <gml:surfaceMember>
                        <gml:Polygon>
                            <gml:exterior>
                                <gml:LinearRing>
                                    <gml:coordinates>20,20 30,20 30,30 20,30 20,20</gml:coordinates>
                                </gml:LinearRing>
                            </gml:exterior>
                        </gml:Polygon>
                    </gml:surfaceMember>
                </gml:MultiSurface>
            </bldg:lod2MultiSurface>
            <bldg:BuildingPart>
                <bldg:measuredHeight>10.0</bldg:measuredHeight>
                <bldg:lod2Solid>
                    <gml:Solid>
                        <gml:exterior>
                            <gml:CompositeSurface>
                                <gml:surfaceMember>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>30 20 0 35 20 0 35 25 0 30 25 0 30 20 0</gml:posList>
                                            </gml:LinearRing>
                                        </gml:exterior>
                                    </gml:Polygon>
                                </gml:surfaceMember>
                            </gml:CompositeSurface>
                        </gml:exterior>
                    </gml:Solid>
                </bldg:lod2Solid>
            </bldg:BuildingPart>
        </bldg:Building>
    </cityObjectMember>
</CityModel> 