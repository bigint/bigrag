"use client";

import { use } from "react";
import { GoogleDrivePanel } from "../../components/google-drive-panel";

const GoogleDriveConnector = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);

  return <GoogleDrivePanel collection={name} />;
};

export default GoogleDriveConnector;
