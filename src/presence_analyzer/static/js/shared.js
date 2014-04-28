google.load("visualization", "1", {packages:["corechart", "timeline"], 'language': 'pl'});

function parseInterval(value) {
    var result = new Date(1,1,1);
    result.setMilliseconds(value*1000);
    return result;
}
