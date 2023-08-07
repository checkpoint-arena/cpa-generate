renamed = 0
Dir.glob("**/*.{avif,png}") do |fn|
    from = fn
    to = fn.sub("portrait_m_", "mportrait_").sub("portrait_w_", "wportrait_").sub("_.png", ".png").sub("_.avif", ".avif")
    if to != from
        File.rename(from, to)
        renamed += 1
    end
end

puts "Renamed #{renamed} files"