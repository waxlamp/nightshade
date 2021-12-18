{
  description = "Nightshade: tools for retrieving movie data from Rotten Tomatoes";

  outputs = { self, nixpkgs }: {
    devShell.x86_64-linux =
      let
        pkgs = nixpkgs.legacyPackages.x86_64-linux;
      in pkgs.mkShell {
        buildInputs = with pkgs.python38Packages; [
          beautifulsoup4
          nltk
          poetry
          pydantic
          requests
        ];
      };
  };
}
