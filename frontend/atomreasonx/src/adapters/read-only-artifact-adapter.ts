export interface ReadOnlyArtifactAdapter {
  manifestPath: string;
  readArtifact(artifactId: string): Promise<unknown>;
}

export const createReadOnlyArtifactAdapter = (
  manifestPath: string,
  readLocalArtifact: (artifactId: string) => Promise<unknown>,
): ReadOnlyArtifactAdapter => ({
  manifestPath,
  readArtifact(artifactId) {
    return readLocalArtifact(artifactId);
  },
});
