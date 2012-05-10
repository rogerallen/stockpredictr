// my utility FIXME review
var float = function(s) {
    return 1.0*s;
}

// ======================================================================
// Numline - vertical line of datapoints.  either left or right
//                  |
//                  | <---- 15.00 name one
//  SYMB 13.13 ---> |
//                  | <---- 12.00 name two
//                  |
// ======================================================================
function Numline(separation_x,font) {
    this.paper         = 0;
    this.datapoints    = []
    this.value_min     = 0.0;
    this.value_max     = 0.0;
    this.window_width  = 0.0;
    this.window_height = 0.0;
    this.left_label_x  = separation_x;
    this.center_line_x = 2*separation_x;
    this.right_label_x = 3*separation_x;
    this.line_height   = 18;
    this.font          = font;
}

Numline.prototype.construct = function(paper, datapoints, window_width, window_height) {
    this.paper         = paper;
    this.datapoints    = datapoints;
    this.window_width  = window_width;
    this.window_height = window_height;
    this.set_minmax()
    this.construct_center_line();
    this.construct_datapoints();
}

Numline.prototype.set_minmax = function() {
    this.value_min = float(this.datapoints[0].value);
    this.value_max = float(this.datapoints[0].value);
    for(i=1; i < this.datapoints.length; i++) {
        this.value_min = Math.min(this.value_min, float(this.datapoints[i].value));
        this.value_max = Math.max(this.value_max, float(this.datapoints[i].value));
    }
    this.value_min -= 0.5;
    this.value_max += 0.5;
}

Numline.prototype.construct_center_line = function() {
    // center line
    var center_line = this.paper.path([["M", this.center_line_x, 0], 
                                   ["L", this.center_line_x, this.window_height]]);
    for(i=Math.ceil(this.value_min); i < this.value_max; i += 1) {
        this.paper.path([["M", this.center_line_x-5, this.scaled_y(i)],
                     ["L", this.center_line_x+5, this.scaled_y(i)]]);
        t = this.paper.text(this.center_line_x, this.scaled_y(i), 
                        i+".00");
        t.attr('font',this.font);
        t.translate(-t.getBBox().width/2-8, 0);
    }
}

Numline.prototype.construct_datapoints = function() {
    var num_right = 0;
    var num_left = 0;
    for(i=0; i < this.datapoints.length; i++) {
        this.datapoints[i].configure(this.paper,this.font);
        if(this.datapoints[i].location === LOCATION.RIGHT) {
            num_right++;
        } else {
            num_left++;
        }
    }
    var right_label_y = this.window_height/2 + Math.floor(num_right/2)*this.line_height;
    var left_label_y  = this.window_height/2 + Math.floor(num_left/2)*this.line_height;
    for(i=0; i < this.datapoints.length; i++) {
        value_y = this.scaled_y(float(this.datapoints[i].value));
        if(this.datapoints[i].location === LOCATION.RIGHT) {
            this.datapoints[i].construct(this.right_label_x, right_label_y,
                                         this.center_line_x, value_y);
            right_label_y -= this.line_height;
        } else {
            this.datapoints[i].construct(this.left_label_x, left_label_y,
                                         this.center_line_x, value_y);
            left_label_y -= this.line_height;
        }
    }
}

Numline.prototype.scaled_y = function(y) {
    var s = 1 - (float(y) - this.value_min)/(this.value_max - this.value_min);
    return s*this.window_height;
}

// ======================================================================
// Datapoint
// ======================================================================
LOCATION = {
    RIGHT: 0,
    LEFT: 1
}

function Datapoint(name,value,location) {
    this.name        = name;
    this.value       = value;
    this.location    = location;
    this._highlight  = false;
    this.paper       = 0;
    this.font        = 0;
    this.paper_text  = 0;
    this.paper_arrow = 0;
}

Datapoint.prototype.highlight = function() {
    this._highlight = true;
}

Datapoint.prototype.configure = function(paper,font) {
    this.paper = paper;
    this.font  = font;
}

Datapoint.prototype.construct = function(label_x,label_y,value_x,value_y) {
    if(this.location === LOCATION.RIGHT) {
        dp_str       = this.value+" "+this.name;
        dp_direction = 1;
        dp_x1        = value_x;
        dp_y1        = value_y;
        dp_x2        = label_x;
        dp_y2        = label_y;
        dp_arrow1    = true;
        dp_arrow2    = false;
    } else {
        dp_str       = this.name+" "+this.value;
        dp_direction = -1;
        dp_x1        = label_x;
        dp_y1        = label_y;
        dp_x2        = value_x;
        dp_y2        = value_y;
        dp_arrow1    = false;
        dp_arrow2    = true;
    }
    the_font = (this._highlight) ? "bold " + this.font : this.font;
    this.paper_text = this.paper.text(label_x, label_y, dp_str);
    this.paper_text.attr('font', the_font);
    this.paper_text.translate(dp_direction*this.paper_text.getBBox().width/2, 0);
    this.paper_arrow = this.arrow(dp_x1,dp_y1,
                                  dp_x2,dp_y2,
                                  dp_arrow1, dp_arrow2); 
    if(this._highlight) {
        this.paper_arrow.attr("stroke-width","2");
    }
}

Datapoint.prototype.arrow = function(x1,y1,x2,y2,arrow1,arrow2) {
    var dx = Math.abs(x2-x1);
    var path = [["M", x1, y1], ["C", x1+dx/2, y1, x2-dx/2, y2, x2, y2]];
    var curve = this.paper.path(path);
    if(arrow1) {
        str = "M"+x1+","+y1+" ";
        str += "l5,-5 l0,10 z";
        pth = this.paper.path(str);
        pth.attr('fill',"#000");
    }
    if(arrow2) {
        str = "M"+x2+","+y2+" ";
        str += "l-5,-5 l0,10 z";
        pth = this.paper.path(str);
        pth.attr('fill',"#000");
    }
    return curve;
}

// ======================================================================
// StockNumline
// ======================================================================
function StockNumline() {
    this.font = '14px Verdana';
    this.numline = new Numline(100.0,this.font);
} 

StockNumline.prototype.construct = function(paper,data,w,h) {
    var datapoints = new Array();
    var min_delta = float(data.price.value);
    datapoints.push(new Datapoint(data.price.name, data.price.value, LOCATION.LEFT));
    for(i=0; i < data.predictions.length; i++) {
        datapoints.push(
            new Datapoint(data.predictions[i].name, data.predictions[i].value, LOCATION.RIGHT));
        min_delta = Math.min(min_delta,
                             Math.abs(float(data.predictions[i].value)-float(data.price.value)))
    }
    datapoints[0].highlight();
    for(i=1; i < datapoints.length; i++) {
        if(min_delta === Math.abs(float(datapoints[i].value)-float(data.price.value))) {
            datapoints[i].highlight();
        }
    }
    this.numline.construct(paper,datapoints,w,h)
}    




