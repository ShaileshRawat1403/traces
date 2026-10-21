import { api } from "../../api/client";
import { EndpointView } from "./EndpointView";

export const ComponentsPage = () => (
  <EndpointView name="components" title="Components" intro="Deterministic components and layers with claim counts by label." fetcher={api.components} />
);
export const RoutesPage = () => (
  <EndpointView name="routes" title="Routes" intro="Route and API inventory with the status of each route claim." fetcher={api.routes} />
);
