const vars = dataform.projectConfig.vars || {};

module.exports = {
  bronze: vars.bronzeDataset || "bronze",
  silver: vars.silverDataset || "silver",
  gold: vars.goldDataset || "gold",
};
