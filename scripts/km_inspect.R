suppressPackageStartupMessages({library(scanMiR); library(scanMiRData)})
mods <- getKdModels("hsa")
m1 <- mods[[1]]
cat("class:", paste(class(m1), collapse=","), "\n")
cat("names:", paste(names(m1), collapse=", "), "\n")
str(m1, max.level = 1)
