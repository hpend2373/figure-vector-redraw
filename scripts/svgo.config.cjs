// svgo settings for vectorizer-style traced SVGs (a <mask> alpha layer + many paths).
// Keeps ids (the mask is referenced by id) and does not merge paths (merging breaks
// the stacking order of traced layers). Typically shrinks files 4-5x.
//
//   npx svgo@3.3.2 --config scripts/svgo.config.cjs -i in.svg -o out.svg
module.exports = {
  multipass: false,
  floatPrecision: 1,
  plugins: [
    {
      name: 'preset-default',
      params: { overrides: { cleanupIds: false, mergePaths: false } },
    },
  ],
};
