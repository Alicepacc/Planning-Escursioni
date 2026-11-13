# GraphHopper per il routing escursionistico (vedi docs/decisions/0002-motore-di-routing.md).
FROM eclipse-temurin:21-jre
ARG GH_VERSION=11.1
WORKDIR /data/graphhopper
ADD https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/${GH_VERSION}/graphhopper-web-${GH_VERSION}.jar /opt/graphhopper.jar
COPY graphhopper/config.yml /opt/config.yml
ENV JAVA_OPTS="-Xmx4g -Xms1g"
EXPOSE 8989
# nel container l'estratto è montato in /data/osm e il server ascolta su tutte le interfacce
CMD ["sh", "-c", "java $JAVA_OPTS \
  -Ddw.graphhopper.datareader.file=/data/osm/trentino-alto-adige.osm.pbf \
  -Ddw.server.application_connectors[0].bind_host=0.0.0.0 \
  -jar /opt/graphhopper.jar server /opt/config.yml"]
